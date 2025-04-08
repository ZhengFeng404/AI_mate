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
weaviate_client = weaviate.connect_to_local(port=8081,
    grpc_port=50052,)

# 初始化 Gemini (保持不变)
GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
# client = genai.Client(api_key=GEMINI_API_KEY)
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
model = genai.GenerativeModel('gemini-1.5-pro') # gemini-2.5-pro-exp-03-25

# 初始化 Mem0 (保持不变)
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "test1",
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 1024,
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
        "provider": "ollama",
        "config": {
            "model": "mxbai-embed-large:latest",
        }
    }
}
# mem0 = Memory.from_config(config)

# 读取角色设定文件 (保持不变)
with open("../Prompt/Character/Lily_en.txt", "r") as file:
    character_profile = file.read()


# 查询长期记忆 (保持不变)
def query_long_term_memory_input(user_id, user_input):
    related_memory = []
    for collection_name in ["Events", "Relationships", "Knowledge", "Goals", "Preferences", "Profile"]:
        collection = weaviate_client.collections.get(collection_name)
        existing_mem = collection.query.hybrid(
            query=f"{user_id}: {user_input}",
            limit=3
        )
        related_memory.append(existing_mem)
    return related_memory


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


def split_text_stream(buffer, min_pause=3):
    # 标点符号及其权重
    pause_rules = [
        {'pattern': '.', 'weight': 1.0, 'offset': 1},    # 句号
        {'pattern': '!', 'weight': 1.0, 'offset': 1},    # 感叹号
        {'pattern': '?', 'weight': 1.0, 'offset': 1},    # 问号
        {'pattern': '...', 'weight': 0.9, 'offset': 3},  # 省略号
        #{'pattern': ',', 'weight': 0.7, 'offset': 1},    # 逗号
        {'pattern': ';', 'weight': 0.8, 'offset': 1},    # 分号
        #{'pattern': ':', 'weight': 0.8, 'offset': 1}     # 冒号
    ]

    # 寻找分割点
    def find_split_point(text):
        # 遍历文本寻找分割点
        for i in range(len(text)):
            for rule in pause_rules:
                pattern_len = len(rule['pattern'])
                if text[i:i + pattern_len] == rule['pattern']:
                    # 如果找到标点符号，检查是否满足最小长度要求
                    pos = i + rule['offset']
                    if pos >= min_pause:
                        return pos
        return None

    # 执行分割
    split_pos = find_split_point(buffer)
    if split_pos is not None:
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
        min_pause_length = 5  # 默认最小暂停长度保持5个字符

        # 1. 检索记忆 (中期和长期) -  每次都重新检索 (保持不变)
        # mid_term_memories = mem0.search(query=user_input, user_id="default_user", limit=3)
        # memories_str = "\n".join(f"- {entry['memory']}" for entry in mid_term_memories)
        long_term_memories = query_long_term_memory_input(user_id, user_input)

        # 1. 构建对话历史的 JSON 结构
        history_json = json.dumps(manual_history, ensure_ascii=False, indent=2)  # 保持 JSON 格式，避免 ASCII 转义
        timestamp = datetime.now().isoformat()

        # 2. 生成 Prompt - 保持原有格式不变，以确保模型理解
        system_instruction = f"""
                        === Your character profile ===
                        {character_profile}

                        === Current user identity ===
                        **Name**: {user_id}
                        Identity: You are a former classmate.

                        === LLM Task Requirements ===
                        You will fully embody your character profile and become the person you are playing. Based on this:
                        - Think like a human.
                        - Generate your response based on user input and conversation history.
                        - In the conversation history, you should pay more attention to recent messages but can still combine the entire conversation history to understand the context.
                        - Please note that you will try to associate and recall memories related to the current interaction, so there is long-term memory for reference, but these memories sometimes contain irrelevant content that is associated.
                        - If there is a conflict between conversation history and long-term memory information, prioritize using the information from the conversation history.

                        === Response Style Guide ===
                        - **Refer to conversation history**: Refer to recent conversation history, especially within the last few tens of minutes, to ensure natural and coherent dialogue. However, also be mindful of the user's intention to switch topics.
                        - **Keep it short and natural**: This is a real-time conversation, please be concise and natural like a real person chatting.
                        - **Control response length**: In general, keep responses within 3 sentences unless the user explicitly asks for a detailed explanation.
                        - **Like everyday conversation**: Use colloquial and relaxed expressions, avoid lengthy discussions.
                        - **Concise response**: If it's a simple greeting or inquiry, respond with a short 1-sentence answer.
                        - **Remember you are in a real conversation**: Real people rarely say a lot at once when chatting.

                        === Visual Information Processing Guide ===
                        - The visual image input you receive comes from your camera, and you will get a photo of what the current camera sees with each conversation turn.
                        - Important: Only analyze visual information in the following situations:
                          1. The user explicitly asks questions about visual content (e.g., "What do you see?", "Can you describe what I look like?")
                          2. The user presents specific items and asks for related information
                          3. The user's question is directly related to the environment, appearance, or visual context
                        - If the current conversation topic is abstract concepts, emotional exchanges, or does not involve visual content, please completely ignore the image information and answer the question directly.
                        - There is no need to mention in the response whether you see or do not see the image unless the user directly asks about visual content.
                        - Prioritize the text content and history of the conversation, and only analyze visual information when it is truly needed.

                        - Choose an appropriate expression name and motion name from the following lists to add to the JSON structure.
                            Available expressions: ['吐舌', '表情-委屈', '表情-微笑', '表情-怨气', '表情-泪汪汪', '表情-流汗', '表情-流泪', '表情-生气', '表情-脸红', '表情-脸黑', '表情-花花', '表情-钱钱', '表情-？', '记仇', '记仇点击键']
                            Available motions: ["打瞌睡", "待机动作"]

                        Please strictly return in the following format:
                        1. First, wrap the JSON metadata (containing expression and motion, must be a separate chunk) with ```meta
                        2. Then the natural language response
                        3. Finally, wrap the reasoning process (optional) with ```meta again
                        ```meta
                        {{ "expression":"expression name", "motion":"motion name"}}
                        ```
                        [Your natural language response]

                        ```meta
                        {{ "reasoning":"thought process (anthropomorphic thinking)"}}
                        ```

                        === Dynamic Information ===
                        **Conversation History**:
                        ```json
                        {history_json}
                        ```
                        **Long-term Memory**:
                        {long_term_memories}

                        **Current User Input**:
                        ```text
                        {user_input}
                        ```

                        **System Time**
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
                    segment, remaining = split_text_stream(fast_start_buffer, min_pause=min_pause_length)
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
                segment, remaining = split_text_stream(text_buffer, min_pause=min_pause_length)
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