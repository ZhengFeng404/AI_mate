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
        self.meta_buffer = ""
        self.in_meta_block = False
        self.metadata = {"expression": "normal", "motion": "idle"}

    def feed(self, chunk_text):
        segments = []

        if not self.in_meta_block:
            # 检测元数据块起始标记
            if "```meta" in chunk_text:
                self.in_meta_block = True
                chunk_text = chunk_text.split("```meta")[-1]

        if self.in_meta_block:
            # 检测元数据块结束标记
            if "```" in chunk_text:
                meta_part, remaining = chunk_text.split("```", 1)
                self.meta_buffer += meta_part

                try:
                    self.metadata.update(json.loads(self.meta_buffer))
                    print(f"🟢 成功解析元数据: {self.metadata}")
                except Exception as e:
                    print(f"🔴 元数据解析失败: {e}")

                # 重置状态
                self.in_meta_block = False
                self.meta_buffer = ""

                # 返回元数据后的剩余文本
                return remaining.strip()
            else:
                self.meta_buffer += chunk_text
                return ""
        else:
            return chunk_text


def split_text_stream(buffer):
    split_chars = ['，', '。', '！', '？', '...']
    positions = []

    # 查找所有可能的分割点
    for char in split_chars:
        pos = buffer.find(char)
        while pos != -1:
            positions.append(pos + len(char) - 1)
            pos = buffer.find(char, pos + 1)

    if not positions:
        return None, buffer

    # 选择最合适的分割点（优先后半部分的标点）
    optimal_pos = max(
        [p for p in positions if p < len(buffer) * 0.8],
        default=max(positions, default=-1)
    )

    if optimal_pos == -1:
        return None, buffer

    return buffer[:optimal_pos + 1].strip(), buffer[optimal_pos + 1:].lstrip()

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

                === 当前用户 ===
                {user_id}，身份是你曾经的同学。
                
                === LLM 任务要求 ===
                你将完全代入你的角色档案，成为你扮演的人，在此基础上：
                - 请基于用户输入和 *对话历史* 生成你的回复。
                - **对话历史**中你应该更关注最近的消息，但仍然可以结合整个对话历史来理解上下文。
                - 请注意，你会尝试联想回忆和目前互动有关的记忆，所以有**长期记忆**可以参考，但这些记忆中有时存在联想到的无关内容。
                - 若对话历史和长期记忆信息有冲突，优先使用对话历史的信息。
                - 你收到的视觉图片输入来自你的摄像头，每次对话时都会获得一张当前摄像头看到的照相。
                - 你应该自行判断历史和图片信息是否与当前对话相关，并自然地将*真正相关*的信息融入到你的语言回复中。
                
                - 选择合适的表情名称、动作名称加入到 JSON 结构中。
                    可用表情：["黑脸", "白眼", "拿旗子", "眼泪"]
                    可用动作：["好奇", "瞌睡", "害怕", "举白旗", "摇头", "抱枕头"]

                请严格按以下格式返回响应：
                1. 首先用 ```meta 包裹JSON元数据（必须单独成块）
                2. 随后是自然语言回复（按标点分块输出）
                ```meta
                {{ "reasoning":"思考过程（拟人化思考）","expression":"表情名称", "motion":"动作名称"}}
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


        # 异步处理流式响应
        json_buffer = ""
        response_text_buffer = ""
        header_parsed = False
        result = {
            "expression": "normal",
            "motion": "idle",
            "reasoning": "",
            "response_text": ""
        }

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


