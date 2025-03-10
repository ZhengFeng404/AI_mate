import json
import os
import asyncio
from datetime import datetime
import google.generativeai as genai
from utils.utils import load_api_key

GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
#embedding_model_name = 'models/text-embedding-004'
memory_process_model = genai.GenerativeModel('gemini-1.5-pro') # PRO?

HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def add_to_history(user_id, user_text, response_text, history):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": timestamp,
        "user_id": user_id,
        "user_text": user_text,
        "ai_response": response_text
    }
    history.setdefault(user_id, []).append(entry)
    manage_history_size(user_id, history)
    save_history(history)

def manage_history_size(user_id, history, max_tokens=8000, summary_limit=2000, summary_sentence_limit=10):
    if user_id not in history:
        return

    # 保留最近的100条对话
    # history[user_id] = history[user_id][-100:]

    # 计算总tokens（假设每个字符0.5个token）
    total_tokens = sum(
        (len(entry.get("user_text", "")) + len(entry.get("ai_response", ""))) // 2
        for entry in history[user_id]
    )

    # 超过max_tokens时生成摘要
    if total_tokens > max_tokens:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. 格式化对话历史文本 (包含时间戳)
        formatted_history_text = ""
        for entry in history[user_id]:
            entry_timestamp = entry.get("timestamp", "") # 获取时间戳
            user_text = entry.get("user_text", "")
            ai_response = entry.get("ai_response", "")
            if user_text and ai_response:
                formatted_history_text += f"[{entry_timestamp}] 用户{user_id}: {user_text}\n[{entry_timestamp}] 虚拟人格: {ai_response}\n" #  在每行对话前添加时间戳

        with open("../Prompt/Character/Lily.txt", "r", encoding="utf-8") as file:
            character_profile = file.read()
        # 2. 构建 Prompt (Prompt 内容保持不变)
        prompt = f"""
        === 你的角色档案 ===
        {character_profile}

        === 当前用户 ===
        {user_id}，身份是你曾经的同学。

        === LLM 任务要求 ===
        你将进行沉浸式角色扮演，成为你扮演的人，在此基础上：
        
        像写日记一样总结以下对话历史。

        本次总结将被用于为后续对话提供上下文，因此需要捕捉理解对话轨迹所需的必要信息。

        请使用中文总结，并限制在{summary_sentence_limit}句以内。

        对话历史:
        {formatted_history_text}
        """

        # 3. 调用 LLM 生成摘要 (代码保持不变)
        try:
            summary_response = memory_process_model.generate_content(prompt)
            summary_text = summary_response.text
        except Exception as e:
            print(f"摘要生成失败: {e}")
            summary_text = "摘要生成失败，请查看日志"

        summary_entry = {
            "timestamp": timestamp,
            "user_id": user_id,
            "ai_response": summary_text,
            "type": "summary"
        }
        # 保留最近50轮对话并添加摘要
        history[user_id] = [summary_entry] + history[user_id][-50:]

    # 清理过旧摘要 (代码保持不变)
    summaries = [entry for entry in history[user_id] if entry.get("type") == "summary"]
    total_summary_tokens = sum(
        len(entry.get("ai_response", "")) // 2
        for entry in summaries
    )
    if total_summary_tokens > summary_limit:
        # 按时间排序摘要并删除最早的三个
        summary_indices = [i for i, entry in enumerate(history[user_id]) if entry.get("type") == "summary"]
        sorted_indices = sorted(summary_indices, key=lambda i: history[user_id][i]["timestamp"])
        for index in reversed(sorted_indices[:3]):
            del history[user_id][index]