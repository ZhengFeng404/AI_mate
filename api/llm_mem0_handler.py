# llm_handler.py
import google.generativeai as genai
# from google import genai
from dotenv import load_dotenv
import os
import json
import weaviate
from mem0 import Memory  # 导入 Mem0
import logging
import base64  # 导入 base64 库，虽然这里可能不是必须的，但在处理图像数据时，导入总是有备无患
import time
from utils.utils import load_api_key
from datetime import datetime
import asyncio
from PIL import Image
import io
import re

load_dotenv()

# 初始化 Weaviate 客户端 (保持不变)

# 初始化 Gemini (保持不变)
GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
# client = genai.Client(api_key=GEMINI_API_KEY)
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
model = genai.GenerativeModel('gemini-1.5-pro')

# 初始化 Mem0 (保持不变)
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "experiment",
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 3072,
        }
    },
    "llm": {
        "provider": "gemini",
        "config": {
            "model": "gemini-2.0-flash",
            "temperature": 0.2,
            "max_tokens": 1500,
        }
    },
    "embedder": {
        "provider": "gemini",
        "config": {
            "model": "models/gemini-embedding-exp-03-07",
        }
    }
}
mem0 = Memory.from_config(config)

# 读取角色设定文件 (保持不变)
with open("../Prompt/Character/Lily.txt", "r", encoding="utf-8") as file:
    character_profile = file.read()


# TODO: check if adding user_id in prompt can let AI distinguish user identity in future memory
def llm_response_generation(user_input, user_id, user_chat_sessions, manual_history,
                            image_base64=None):  # 添加 manual_history 参数
    """
    主 LLM 回复生成函数 (使用手动维护的对话历史).

    Args:
        user_input (str): 用户输入的文本
        user_id (str): 用户 ID
        user_chat_sessions (dict): 仍然保留，但可能不再直接使用 ChatSession 对象 (可以用于其他用户相关数据存储)
        manual_history (list): 手动维护的对话历史列表  <- 新增 manual_history 参数
        image_base64 (str, optional): 用户输入的图像 Base64 字符串，默认为 None

    Returns:
        dict: 包含回复信息的字典 (response_text, expression, motion 等)
    """
    # 1.  不再需要获取或创建 ChatSession 对象

    # 2. 调用 get_gemini_response_with_history 获取 Gemini 回复 (修改部分)
    gemini_response_dict = get_gemini_response_with_history(user_input, user_id, manual_history,
                                                            image_base64=image_base64)  # 传递 manual_history

    # 3. 返回结果 (保持不变)
    return gemini_response_dict


class MetadataParser:
    def __init__(self):
        self.state = "init"  # 状态：init | meta_started | meta_parsing
        self.buffer = ""
        self.metadata = {"expression": "normal", "motion": "idle", "reasoning": ""}

    def feed(self, chunk):
        output = ""
        self.buffer += chunk

        while True:
            if self.state == "init":
                # 第一阶段：检测初始反引号
                idx = self.buffer.find('```')
                if idx == -1:
                    output += self.buffer
                    self.buffer = ""
                    break

                # 分离前导文本
                output += self.buffer[:idx]
                self.buffer = self.buffer[idx + 3:]
                self.state = "meta_started"  # 进入第二阶段

            elif self.state == "meta_started":
                # 第二阶段：检测后续meta关键字
                if len(self.buffer) >= 4:
                    if self.buffer.startswith("meta"):
                        # 找到完整起始标记
                        self.buffer = self.buffer[4:]
                        self.state = "meta_parsing"
                        self.meta_content = ""
                    else:
                        # 非meta块，回退初始状态
                        output += '```' + self.buffer
                        self.buffer = ""
                        self.state = "init"
                    break
                else:
                    # 保留不完整数据等待下个chunk
                    break

            elif self.state == "meta_parsing":
                # 第三阶段：解析元数据内容
                end_idx = self.buffer.find('```')
                if end_idx == -1:
                    self.meta_content += self.buffer
                    self.buffer = ""
                    break

                # 提取完整元数据
                self.meta_content += self.buffer[:end_idx]
                self.buffer = self.buffer[end_idx + 3:]
                self._parse_meta_content()
                self.state = "init"  # 重置状态
        return output

    def _parse_meta_content(self):
        try:
            data = json.loads(self.meta_content.strip())
            self.metadata.update({
                "expression": data.get("expression", "normal"),
                "motion": data.get("motion", "idle"),
                "reasoning": data.get("reasoning", "")
            })
            print(f"✅ 元数据更新: {self.metadata}")
        except Exception as e:
            print(f"❌ 元数据解析失败: {str(e)}")
            print(f"错误内容: {self.meta_content}")


def split_text_stream(buffer, max_chunk=20, min_pause=3):
    # 增强版自然停顿符号（带权重机制）
    pause_rules = [
        {'pattern': '\n\n', 'weight': 1.0, 'offset': 2},  # 段落分隔
        {'pattern': '。', 'weight': 0.95, 'offset': 1},  # 句号
        {'pattern': '！', 'weight': 0.9, 'offset': 1},  # 感叹号
        {'pattern': '？', 'weight': 0.9, 'offset': 1},  # 问号
        {'pattern': '...', 'weight': 0.85, 'offset': 3},  # 中文省略号
        {'pattern': '……', 'weight': 0.85, 'offset': 2},  # 中文长省略
        {'pattern': '，', 'weight': 0.7, 'offset': 1},  # 中文逗号
        {'pattern': ',', 'weight': 0.65, 'offset': 1},  # 英文逗号
        {'pattern': '、', 'weight': 0.6, 'offset': 1},  # 顿号
        {'pattern': ' ', 'weight': 0.5, 'offset': 1}  # 空格
    ]

    # 智能寻找最优分割点
    def find_optimal_split(text):
        candidates = []

        # 遍历所有可能的断点
        for i in range(min(len(text), max_chunk + 25)):
            for rule in pause_rules:
                pattern_len = len(rule['pattern'])
                if text[i:i + pattern_len] == rule['pattern']:
                    score = rule['weight'] * (1 - abs(i - max_chunk) / max_chunk)
                    pos = i + rule['offset']
                    candidates.append((pos, score))
                    break  # 优先匹配长pattern

        # 筛选有效候选
        valid = [c for c in candidates if c[0] >= min_pause and c[0] <= max_chunk + 5]
        if valid:
            best = max(valid, key=lambda x: x[1])
            return best[0]

        # 保底策略：在max_chunk处强制分割
        return min(max_chunk, len(text))

    # 执行分割
    if len(buffer) > max_chunk * 1.2:  # 允许10%溢出
        split_pos = find_optimal_split(buffer)
        if split_pos > min_pause:
            return buffer[:split_pos].strip(), buffer[split_pos:].lstrip()

    return None, buffer


def might_need_visual_info(user_input, recent_history=None):
    """
    判断当前对话是否可能需要视觉信息

    Args:
        user_input: 用户输入文本
        recent_history: 最近的对话历史 (可选)

    Returns:
        bool: 是否可能需要视觉信息
    """
    # 视觉相关关键词
    visual_keywords = [
        "看", "瞧", "观察", "图", "照片", "图像", "图片", "相片", "样子", "长相",
        "外表", "外貌", "衣服", "穿着", "颜色", "见到", "眼前", "画面", "屏幕",
        "看到", "看见", "图中", "显示", "出现", "observe", "see", "look", "photo",
        "picture", "image", "appearance", "camera", "screen", "visible", "show"
    ]

    # 视觉询问模式
    visual_patterns = [
        r"你[能看]*?看[到见]*?[了吗什么]",
        r"[能可][以否]看[到见]",
        r"[能可][以否]描述",
        r"[能可][以否]告诉我你[看见]*?到[了什么]",
        r"这[是长看]什么",
        r"这个[东西物]是",
        r"我[的穿戴拿]着",
        r"[能可][否以]认出",
        r"你觉得[这我][个人]?[怎样如何]",
        r"[你有].*[摄像头相机]"
    ]

    # 1. 检查关键词匹配
    for keyword in visual_keywords:
        if keyword in user_input:
            return True

    # 2. 检查语义模式匹配
    for pattern in visual_patterns:
        if re.search(pattern, user_input):
            return True

    # 3. 检查最近的对话历史是否与视觉相关 (如有)
    if recent_history and len(recent_history) > 0:
        last_exchange = recent_history[-1]
        if "ai_response" in last_exchange:
            last_response = last_exchange["ai_response"]
            # 如果AI最近回复中提到了视觉内容，用户可能在跟进视觉话题
            for keyword in visual_keywords:
                if keyword in last_response:
                    return True

    # 默认情况下，不需要视觉信息
    return False


async def get_gemini_response_with_history(user_input, user_id, manual_history,
                                           image_base64=None):  # 修改函数签名，添加 manual_history
    """
    使用 手动维护的对话历史，调用 Gemini 生成回复.

    Args:
        user_input (str): 用户输入的文本
        user_id (str): 用户 ID
        manual_history (list): 手动维护的对话历史列表  <- 新增 manual_history 参数
        image_base64 (str, optional): 用户输入的图像 Base64 字符串，默认为 None
    """
    try:
        # 初始化状态
        text_buffer = ""
        meta_parser = MetadataParser()
        has_yielded_first_chunk = False  # 跟踪是否已输出首个文本块
        default_metadata = {"expression": "normal", "motion": "idle"}  # 默认元数据

        # 设置更短的文本分段长度，使对话更自然
        max_chunk_length = 15  # 默认分段长度减少到15个字符
        min_pause_length = 3  # 默认最小暂停长度保持3个字符

        # 1. 检索记忆 (中期和长期) -  每次都重新检索 (保持不变)
        mid_term_memories = mem0.search(query=user_input, user_id=user_id, limit=5)
        memories_str = "\n".join(f"- {entry['memory']}" for entry in mid_term_memories)
        # long_term_memories = query_long_term_memory_input(user_id, user_input)
        print(f"mid_term memory: ",memories_str)

        # 1. 构建对话历史的 JSON 结构
        history_json = json.dumps(manual_history, ensure_ascii=False, indent=2)  # 保持 JSON 格式，避免 ASCII 转义
        timestamp = datetime.now().isoformat()

        # 2. 生成 Prompt - 保持原有格式不变，以确保模型理解
        system_instruction = f"""
                === 你的角色档案 ===
                {character_profile}

                === 当前用户身份 ===
                **名字**：{user_id}
                身份：是你曾经的同学。

                === LLM 任务要求 ===
                你将完全代入你的角色档案，成为你扮演的人，在此基础上：
                - 像人一样思考。
                - 基于用户输入和对话历史生成你的回复。
                - 对话历史中你应该更关注最近的消息，但仍然可以结合整个对话历史来理解上下文。
                - 请注意，你会尝试联想回忆和目前互动有关的记忆，所以有长期记忆可以参考，但这些记忆中有时存在联想到的无关内容。
                - 若对话历史和长期记忆信息有冲突，优先使用对话历史的信息。

                === 回复风格指南 ===
                - **参考对话历史**：参考近期的对话历史，尤其是最近几十分钟内的，让前后对话自然连贯，但是注意兼顾用户切换话题的意愿。
                - **保持简短自然**：这是实时对话，请像真人聊天一样简洁自然。
                - **控制回复长度**：一般情况下，回复保持在3句话以内，除非用户明确要求详细解释。
                - **像日常对话一样**：使用口语化、轻松的表达方式，避免长篇大论。
                - **简洁回应**：如果是简单问候或询问，用简短1句话回应即可。
                - **记住你是真人对话**：真实的人在聊天时很少一次性说很多话。

                === 视觉信息处理指南 ===
                - 你收到的视觉图片输入来自你的摄像头，每次对话时都会获得一张当前摄像头看到的照片。
                - 重要：仅在以下情况分析视觉信息：
                  1. 用户明确询问关于视觉内容的问题（如"你看到什么？"、"能描述一下我的样子吗？"）
                  2. 用户出示特定物品并询问相关信息
                  3. 用户的问题与环境、外观或视觉上下文直接相关
                - 如果当前对话主题是抽象概念、情感交流或不涉及视觉内容，请完全忽略图像信息，直接回答问题。
                - 不需要在回复中提及你看到或没看到图像，除非用户直接询问视觉内容。
                - 优先考虑对话的文本内容和历史，只有在真正需要时才分析视觉信息。

                - 从以下列表中选择合适的表情名称、动作名称加入到 JSON 结构中。
                    可用表情：['吐舌', '表情-委屈', '表情-微笑', '表情-怨气', '表情-泪汪汪', '表情-流汗', '表情-流泪', '表情-生气', '表情-脸红', '表情-脸黑', '表情-花花', '表情-钱钱', '表情-？', '记仇', '记仇点击键']
                    可用动作：["打瞌睡", "待机动作"]

                请严格按以下格式返回：
                1. 首先用 ```meta 包裹JSON元数据（包含表情和动作，必须独立成chunk）
                2. 随后是 ```meta 包裹推理过程
                3. 最后是自然语言回复
                ```meta
                {{ "expression":"表情名称", "motion":"动作名称", "reasoning":"思考过程（拟人化思考）"}}
                ```
                [你的自然语言回复]

                === 动态信息 ===
                **对话历史**:
                ```json
                {history_json}
                ```
                **长期记忆**：
                {memories_str}

                **当前用户输入**:
                ```text
                {user_input}
                ```

                **系统时间**
                {timestamp}         
                """

        # 3. 准备内容 (parts)
        parts = [{"text": system_instruction}]

        # 判断是否需要包含图像
        recent_history = manual_history[-3:] if len(manual_history) >= 3 else manual_history
        needs_visual = might_need_visual_info(user_input, recent_history)

        if image_base64 and needs_visual:
            start_time = time.time()
            print(f"✅ 检测到可能需要视觉信息，将包含图像数据")
            try:
                image_data = base64.b64decode(image_base64)
                image = Image.open(io.BytesIO(image_data))
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                })
                print(f"图像处理耗时: {time.time() - start_time:.4f}秒")
            except Exception as e:
                print(f"Base64 图像数据解码失败: {str(e)}")
        else:
            if image_base64:
                print(f"⏩ 本次对话可能不需要视觉信息，跳过图像处理")

        # 4. 调用 LLM
        start_time_gemini = time.time()

        # 使用设置更高响应性的参数
        generation_config = {
            "temperature": 0.7,  # 保持一定的创造性
            "top_p": 0.95,
            "top_k": 40,
            "candidate_count": 1,
            "max_output_tokens": 1024,  # 减少最大token数，鼓励简短回复
        }



        # 5. 处理流式响应 - 优化初始响应速度
        fast_start_buffer = ""
        meta_seen = False

        async for chunk in await model.generate_content_async(
                contents=parts,
                generation_config=generation_config,
                stream=True
        ):
            raw_text = chunk.text
            if not raw_text:  # 跳过空响应
                continue

            # 记录接收时间
            chunk_receive_time = time.time()
            chunk_latency = chunk_receive_time - start_time_gemini
            print(f"🔴 原始响应块: {repr(raw_text)} (延迟: {chunk_latency:.4f}s)")

            # 优化初始响应：检测元数据与文本的分离
            if not meta_seen and "```meta" in raw_text:
                meta_seen = True

            # 处理元数据块
            processed_text = meta_parser.feed(raw_text)

            # 收集快速启动文本
            if not has_yielded_first_chunk:
                fast_start_buffer += processed_text

                # 快速返回第一个有意义的文本 - 如果满足条件
                if (len(fast_start_buffer) >= 5 and meta_seen) or len(fast_start_buffer) >= 10:  # 降低到10个字符就开始输出
                    # 检查是否有足够文本可以分割
                    segment, remaining = split_text_stream(fast_start_buffer, max_chunk=max_chunk_length,
                                                           min_pause=min_pause_length)
                    if segment:
                        first_chunk_time = time.time() - start_time_gemini
                        print(f"🟢 快速首次响应: {segment} (总耗时: {first_chunk_time:.4f}s)")
                        yield {
                            "type": "segment",
                            "segment": segment,
                            "expression": meta_parser.metadata.get("expression", default_metadata["expression"]),
                            "motion": meta_parser.metadata.get("motion", default_metadata["motion"])
                        }
                        has_yielded_first_chunk = True
                        text_buffer = remaining
                    else:
                        text_buffer = fast_start_buffer
                        has_yielded_first_chunk = True
                else:
                    continue
            else:
                # 处理后续正常流文本
                text_buffer += processed_text

            # 正常处理文本分段，使用较短的分段长度
            while True:
                segment, remaining = split_text_stream(text_buffer, max_chunk=max_chunk_length,
                                                       min_pause=min_pause_length)
                if not segment:
                    break

                # 记录输出时间
                segment_time = time.time() - start_time_gemini
                print(f"🟡 生成段落: {segment} (总耗时: {segment_time:.4f}s)")
                yield {
                    "type": "segment",
                    "segment": segment,
                    "expression": meta_parser.metadata.get("expression", default_metadata["expression"]),
                    "motion": meta_parser.metadata.get("motion", default_metadata["motion"])
                }
                text_buffer = remaining

        # 处理剩余内容
        if text_buffer.strip():
            final_chunk_time = time.time() - start_time_gemini
            print(f"🟡 最终段落: {text_buffer.strip()} (总耗时: {final_chunk_time:.4f}s)")
            yield {
                "type": "segment",
                "segment": text_buffer.strip(),
                "expression": meta_parser.metadata.get("expression", default_metadata["expression"]),
                "motion": meta_parser.metadata.get("motion", default_metadata["motion"])
            }

        print(f"✅ 完成生成，总用时: {time.time() - start_time_gemini:.2f}秒")
    except Exception as e:
        print(f"Stream error: {e}")