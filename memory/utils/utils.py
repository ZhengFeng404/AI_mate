import os
import logging
import json

logging.basicConfig(level=logging.INFO)

def load_api_key(key_name):
    """
    从文件中读取 API Key 并设置为环境变量.

    Args:
        filepath (str): 存储 API Key 的文件路径.

    Returns:
        bool: True 如果 API Key 成功加载并设置，False 如果发生错误.
    """
    try:
        with open("api_key.env", 'r') as f:
            api_key = f.readline().strip() # 读取第一行并去除首尾空白字符
        if not api_key:
            logging.error(f"API Key 文件为空或读取失败")
            return False
        #os.environ[key_name] = api_key
        logging.info("Gemini API Key 从文件成功加载并设置为环境变量。")
        return api_key
    except FileNotFoundError:
        logging.error(f"API Key 文件未找到")
        return False
    except Exception as e:
        logging.error(f"读取 API Key 文件时发生错误: {e}")
        return False


def format_conversation_history(chat_session, user_id):
    history_text = ""
    if chat_session.history:
        for content in chat_session.history:
            role = f"User {user_id}" if content.role == "user" else "AI"
            text = content.parts[0].text.strip()
            if role == "AI" and "response_text" in text:
                try:
                    response_json = json.loads(text.replace('`json', '').replace('`', '').strip())
                    text = response_json.get("response_text", "回复内容解析失败")
                except json.JSONDecodeError:
                    pass
            history_text += f"{role}: {text}\n"
    return history_text