import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import weaviate
from mem0 import Memory  # 导入 Mem0
import logging
import base64 # 导入 base64 库，虽然这里可能不是必须的，但在处理图像数据时，导入总是有备无患
import time
from utils.utils import load_api_key

load_dotenv()

# 初始化 Weaviate 客户端 (保持不变)
client = weaviate.connect_to_local()

# 初始化 Gemini (保持不变)
GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
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
with open("Sunflower_character_profile.txt", "r", encoding="utf-8") as file:
    character_profile = file.read()

# 查询长期记忆 (保持不变)
def query_long_term_memory_input(user_input):
    related_memory = []
    for collection_name in ["Events", "Relationships", "Knowledge", "Goals", "Preferences"]:
        collection = client.collections.get(collection_name)
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


def get_gemini_response_with_history(user_input, user_id, manual_history, image_base64=None): # 修改函数签名，添加 manual_history
    """
    使用 手动维护的对话历史，调用 Gemini 生成回复.

    Args:
        user_input (str): 用户输入的文本
        user_id (str): 用户 ID
        manual_history (list): 手动维护的对话历史列表  <- 新增 manual_history 参数
        image_base64 (str, optional): 用户输入的图像 Base64 字符串，默认为 None

    Returns:
        dict: 包含回复信息的字典 (response_text, expression, motion 等)
    """
    try:
        # 初始化 Gemini 模型 (system instruction 部分保持不变)
        system_instruction = f"""
        {character_profile}

        === 当前用户 ===
        {user_id}

        === LLM任务要求 ===
        你将扮演你的角色。
        请基于用户输入，和之前的*对话历史*，生成你的语言回复。
        请注意，你会尝试联想回忆和目前互动有关的记忆，所以有**长期记忆**可以参考，但这些记忆中有时存在联想到的无关内容。
        你收到的视觉图片输入来自你的摄像头，每次对话时都会获得一张当前摄像头看到的照相。
        你应该自行判断记忆和图片信息是否与当前对话相关，并自然地将*真正相关*的信息融入到你的语言回复中。

        选择合适的表情名称、动作名称加入到JSON输出中。

        请按以下 JSON 格式返回，每个条目都只有一个元素：
        {{
            "expression": "表情名称",
            "motion": "动作名称",
            "response_text": "回复文本（只包括将要说出口的话语）",
        }}

        可用表情："黑脸", "白眼", "拿旗子", "眼泪"
        可用动作："好奇", "瞌睡", "害怕", "举白旗", "摇头", "抱枕头"

        """
        gemini_model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05',
                                             system_instruction=system_instruction)
        chat_session = gemini_model.start_chat(history=[]) #  创建一个临时的 chat_session，但 history 不会被自动维护

        # 1. 检索记忆 (中期和长期) -  每次都重新检索 (保持不变)
        #mid_term_memories = mem0.search(query=user_input, user_id="default_user", limit=3)
        #memories_str = "\n".join(f"- {entry['memory']}" for entry in mid_term_memories)
        long_term_memories = query_long_term_memory_input(user_input)

        # 2. 构建动态 Prompt 模板 (修改部分 -  加入 manual_history)
        prompt_template = f"""
        === 对话历史 ===
        {{manual_history}}

        用户输入：{{user_input}}

        长期记忆：
        {{long_term_memories}}

        请严格按照 JSON 格式返回结果。
        """

        # 3. 准备内容 (parts -  保持不变)
        parts = []

        # 格式化 manual_history 为文本
        formatted_history = ""
        if manual_history:
            formatted_history = "\n".join(manual_history) #  假设 manual_history 是文本列表，每条记录就是一行对话

        parts.append({"text": prompt_template.format(
            manual_history=formatted_history, #  使用格式化后的 manual_history
            user_input=user_input,
            long_term_memories=long_term_memories,
            #mid_term_memories=memories_str
        )})

        start_time_decode = time.time()
        if image_base64:
            try:
                image_data = base64.b64decode(image_base64)
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                })
            except Exception as e:
                print(f"Base64 图像数据解码失败: {str(e)}")
        end_time_decode = time.time()
        decode_time = end_time_decode - start_time_decode
        print(f"Base64 图像数据解码成功. 耗时: {decode_time:.4f} 秒")

        # 4. 使用 gemini_model.generate_content(parts=parts) 发送请求 (保持不变，或根据您使用的库版本调整)
        gemini_response = chat_session.model.generate_content( #  仍然使用 generate_content
            contents=parts)

        # 5. 提取 JSON 内容并解析 (保持不变)
        response_text = gemini_response.text
        json_str = response_text.replace('`json', '').replace('`', '').strip()
        result = json.loads(json_str)

        # 6. 确保所有字段存在 (保持不变)
        required_fields = ['expression', 'motion', 'response_text']
        if not all(field in result for field in required_fields):
            raise ValueError("Missing required fields in response")

        return result

    except Exception as e:
        print(f"Gemini处理失败: {str(e)}")
        return {
            "expression": "normal",
            "motion": "idle",
            "response_text": f"出现了一些问题，{str(e)}"
        }


def test_llm_image_input():
    """
    测试 LLM handler 的图像输入处理能力.
    """
    print("开始测试 LLM 图像输入处理...")

    # 1. 读取测试图片并 Base64 编码
    try:
        with open("test_image.jpg", "rb") as image_file:
            image_data = image_file.read()
            test_image_base64 = base64.b64encode(image_data).decode('utf-8')
        print("测试图片 Base64 编码成功.")
    except FileNotFoundError:
        print("错误: 找不到测试图片 test_image.jpg. 请确保该文件与 llm_handler.py 在同一目录下.")
        return
    except Exception as e:
        print(f"读取测试图片或编码失败: {e}")
        return

    # 2. 准备测试用户输入
    test_user_input_text = "这是我上传的图片，请描述一下图片内容，并给我一个表情和一个动作。"
    test_user_id = "test_user_image_input"
    test_user_chat_sessions = {} #  使用空字典即可，因为测试用例是新的会话

    # 3. 调用 llm_response_generation 函数
    print("调用 llm_response_generation 函数...")
    response_dict = llm_response_generation(
        user_input=test_user_input_text,
        user_id=test_user_id,
        user_chat_sessions=test_user_chat_sessions,
        image_base64=test_image_base64
    )

    # 4. 检查返回结果
    print("检查返回结果...")
    if response_dict and isinstance(response_dict, dict):
        if all(key in response_dict for key in ["expression", "motion", "response_text"]):
            if response_dict["response_text"]:
                print("测试通过!")
                print("返回结果:")
                print(f"  表情: {response_dict['expression']}")
                print(f"  动作: {response_dict['motion']}")
                print(f"  回复文本: {response_dict['response_text']}")
                if "图片" in response_dict["response_text"] or "图像" in response_dict["response_text"] or "描述" in response_dict["response_text"]:
                    print("  回复文本中包含图片相关关键词，初步判断 Gemini 能够理解图像内容。")
                else:
                    print("  回复文本中 **没有** 包含图片相关关键词，可能 Gemini **未能理解图像内容**，请检查测试图片或 Prompt.")
            else:
                print("错误: 返回的 response_text 为空字符串.")
        else:
            print("错误: 返回结果字典缺少必要的字段 (expression, motion, response_text).")
    else:
        print("错误: llm_response_generation 函数没有返回字典，或返回值为 None.")

    print("LLM 图像输入处理测试结束.")
    test_user_id = "test_user_image_input_history_test"  # 修改 user_id 以区分测试
    test_user_chat_sessions = {}  # 确保每次测试都使用新的 chat session 字典

    # 第一轮对话
    test_user_input_text_1 = "这是我上传的图片，请描述一下图片内容，并给我一个表情和一个动作。"
    print("\n--- 第一轮对话 ---")
    response_dict_1 = llm_response_generation(
        user_input=test_user_input_text_1,
        user_id=test_user_id,
        user_chat_sessions=test_user_chat_sessions,
        image_base64=test_image_base64
    )
    print("第一轮返回结果:")
    print(response_dict_1)

    # 第二轮对话 (基于第一轮对话之后)
    test_user_input_text_2 = "谢谢你的描述，那这张图片里还有什么其他的细节吗？"  # 第二轮输入，追问细节
    print("\n--- 第二轮对话 ---")
    response_dict_2 = llm_response_generation(
        user_input=test_user_input_text_2,
        user_id=test_user_id,
        user_chat_sessions=test_user_chat_sessions,
        image_base64=test_image_base64
    )
    print("第二轮返回结果:")
    print(response_dict_2)

    # 检查对话历史 (在第二轮对话后检查)
    chat_session = test_user_chat_sessions[test_user_id]
    print("\n--- 检查对话历史 ---")
    print("完整的对话历史:")
    print(chat_session.history)

    # ... (结果检查代码 - 可以保持不变或根据需要调整) ...
    print("LLM 图像输入处理和对话历史更新测试结束.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO) #  设置日志级别为 INFO， 避免测试输出过于冗余
    test_llm_image_input() # 调用测试函数
