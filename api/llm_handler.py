# llm_handler.py
import google.generativeai as genai
#from google import genai
from dotenv import load_dotenv
import os
import json
import weaviate
from mem0 import Memory  # 导入 Mem0
import logging
import base64 # 导入 base64 库，虽然这里可能不是必须的，但在处理图像数据时，导入总是有备无患
import time
from utils.utils import load_api_key
from datetime import datetime
import asyncio
from PIL import Image
import io

load_dotenv()

# 初始化 Weaviate 客户端 (保持不变)
weaviate_client = weaviate.connect_to_local()

# 初始化 Gemini (保持不变)
GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
#client = genai.Client(api_key=GEMINI_API_KEY)
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

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
#mem0 = Memory.from_config(config)

# 读取角色设定文件 (保持不变)
with open("../Prompt/Character/Lily.txt", "r", encoding="utf-8") as file:
    character_profile = file.read()

# 查询长期记忆 (保持不变)
def query_long_term_memory_input(user_input):
    related_memory = []
    for collection_name in ["Events", "Relationships", "Knowledge", "Goals", "Preferences", "Profile"]:
        collection = weaviate_client.collections.get(collection_name)
        existing_mem = collection.query.hybrid(
            query=f"User: {user_input}",
            limit=2
        )
        related_memory.append(existing_mem)
    return related_memory


# TODO: check if adding user_id in prompt can let AI distinguish user identity in future memory
def llm_response_generation(user_input, user_id, user_chat_sessions, manual_history, image_base64=None): # 添加 manual_history 参数
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
    gemini_response_dict = get_gemini_response_with_history(user_input, user_id, manual_history, image_base64=image_base64) # 传递 manual_history

    # 3. 返回结果 (保持不变)
    return gemini_response_dict


class MetadataParser:
    def __init__(self):
        self.state = "init"  # 状态：init | meta_started | meta_parsing
        self.buffer = ""
        self.metadata = {"expression": "normal", "motion": "idle"}

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
                "motion": data.get("motion", "idle")
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


async def get_gemini_response_with_history(user_input, user_id, manual_history, image_base64=None): # 修改函数签名，添加 manual_history
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
        # 1. 检索记忆 (中期和长期) -  每次都重新检索 (保持不变)
        # mid_term_memories = mem0.search(query=user_input, user_id="default_user", limit=3)
        # memories_str = "\n".join(f"- {entry['memory']}" for entry in mid_term_memories)
        long_term_memories = query_long_term_memory_input(user_input)

        # 1. 构建对话历史的 JSON 结构
        history_json = json.dumps(manual_history, ensure_ascii=False, indent=2)  # 保持 JSON 格式，避免 ASCII 转义
        timestamp = datetime.now().isoformat()
        # 2. 生成 Prompt
        system_instruction = f"""
                === 你的角色档案 ===
                {character_profile}

                === 当前用户身份 ===
                **名字**：{user_id}
                身份：是你曾经的同学。
                
                === LLM 任务要求 ===
                你将完全代入你的角色档案，成为你扮演的人，在此基础上：
                - 像人一样思考。
                - 基于用户输入和 *对话历史* 生成你的回复。
                - **对话历史**中你应该更关注最近的消息，但仍然可以结合整个对话历史来理解上下文。
                - 请注意，你会尝试联想回忆和目前互动有关的记忆，所以有**长期记忆**可以参考，但这些记忆中有时存在联想到的无关内容。
                - 若对话历史和长期记忆信息有冲突，优先使用对话历史的信息。
                - 你收到的视觉图片输入来自你的摄像头，每次对话时都会获得一张当前摄像头看到的照相。
                - 你应该自行判断历史和图片信息是否与当前对话相关，并自然地将*真正相关*的信息融入到你的语言回复中。
                
                - 选择合适的表情名称、动作名称加入到 JSON 结构中。
                    可用表情：["黑脸", "白眼", "拿旗子", "眼泪"]
                    可用动作：["好奇", "瞌睡", "害怕", "举白旗", "摇头", "抱枕头"]

                请严格按以下格式返回：
                1. 首先用 ```meta 包裹JSON元数据（必须独立成chunk）
                2. 随后是自然语言回复
                ```meta
                {{ "reasoning":“思考过程（拟人化思考）”, "expression":"表情名称", "motion":"动作名称"}}
                [你的自然语言回复]
                
                === 动态信息 ===
                **对话历史**:
                ```json
                {history_json}
                ```
                **长期记忆**：
                {long_term_memories}

                **当前用户输入**:
                ```text
                {user_input}
                ```
                
                **系统时间**
                {timestamp}         
                """

        # 3. 准备内容 (parts)
        parts = [{"text": system_instruction}]
        if image_base64:
            try:
                image_data = base64.b64decode(image_base64)
                image = Image.open(io.BytesIO(image_data))
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                })
            except Exception as e:
                print(f"Base64 图像数据解码失败: {str(e)}")

        # 4. 调用 LLM
        start_time_gemini = time.time()
        #gemini_response = client.models.generate_content_stream(model="gemini-2.0-pro-exp-02-05",
        #                                                        contents=[system_instruction, image])


        # 5. 解析 JSON 响应
        model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05')


        async for chunk in await model.generate_content_async(contents=parts,stream=True):
            raw_text = chunk.text
            print(f"🔴 原始响应块: {repr(raw_text)}")

            # 处理元数据块
            processed_text = meta_parser.feed(raw_text)

            # 处理文本流
            text_buffer += processed_text

            # 实时分割
            while True:
                segment, remaining = split_text_stream(text_buffer)
                if not segment:
                    break

                print(f"🟡 生成段落: {segment}")
                yield {
                    "type": "segment",
                    "segment": segment,
                    "expression": meta_parser.metadata["expression"],
                    "motion": meta_parser.metadata["motion"]
                }
                text_buffer = remaining

            # 处理剩余内容
        if text_buffer.strip():
            yield {
                "type": "segment",
                "segment": text_buffer.strip(),
                "expression": meta_parser.metadata["expression"],
                "motion": meta_parser.metadata["motion"]
            }
    except Exception as e:
        print(f"Stream error: {e}")


