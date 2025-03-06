import asyncio
from mem0 import Memory
import os
import functools # 导入 functools
from utils.utils import load_api_key

GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# 初始化 Mem0 (同步代码，保持不变)
config = {
    "vector_store": {
        "provider": "qdrant",  # docker run -p 6333:6333 qdrant/qdrant
        "config": {
            "collection_name": "test1",
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 768,
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
mem0 = Memory.from_config(config)  # 初始化 Mem0 (同步)


# 创建一个同步的 mem0.add 函数的 "partial" 版本，方便在线程中调用
#sync_mem0_add_user = functools.partial(mem0.add, metadata={"identity": "user"})
#sync_mem0_add_ai = functools.partial(mem0.add, metadata={"identity": "ai"})


async def add_to_mem0(user_id, user_input, ai_response):
    """异步存储用户输入和 AI 回复到 Mem0 (使用 asyncio.to_thread)"""
    try:
        mem0.add(f"user:-> {user_input}\nai:-> {ai_response}", user_id=user_id)

        print("Mem0 异步存储完成")
    except Exception as e:
        print(f"Mem0 异步存储失败: {str(e)}")