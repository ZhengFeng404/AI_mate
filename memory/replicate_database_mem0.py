import json
import asyncio
from utils.utils import load_api_key
from mem0 import Memory
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models

GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# 初始化 Qdrant 客户端
qdrant_client = QdrantClient(host="localhost", port=6333)

# 确保集合存在并具有正确的维度
collection_name = "experiment"
try:
    # 检查集合是否存在
    collection_info = qdrant_client.get_collection(collection_name)
    if collection_info.config.params.vectors.size != 3072:
        # 如果维度不匹配，删除并重新创建集合
        qdrant_client.delete_collection(collection_name)
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=3072, distance=models.Distance.COSINE),
        )
except Exception:
    # 如果集合不存在，创建它
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=3072, distance=models.Distance.COSINE),
    )

# 初始化 Mem0 (同步代码，保持不变)
config = {
    "vector_store": {
        "provider": "qdrant",  # docker run -p 6333:6333 qdrant/qdrant
        "config": {
            "collection_name": "experiment",
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 3072,  # 保持与集合配置一致
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

mem0 = Memory.from_config(config)  # 初始化 Mem0 (同步)

def add_to_mem0(user_id, user_input, ai_response, conversation_history):
    try:
        mem0.add(f"user:-> {user_input}\nai:-> {ai_response}", user_id=user_id)
        print("Mem0 异步存储完成")
    except Exception as e:
        print(f"Mem0 异步存储失败: {str(e)}")

async def import_dialogues_to_memory():
    try:
        # 读取对话数据
        with open('30_turns_dialogues.json', 'r', encoding='utf-8') as f:
            dialogues = json.load(f)

        print(f"成功加载 {len(dialogues)} 条对话数据")

        # 为每条对话创建记忆
        for dialogue in dialogues:
            user_id = dialogue["user_id"]
            user_text = dialogue["user_text"]
            ai_response = dialogue["ai_response"]

            # 使用add_to_mem0函数添加记忆
            add_to_mem0(
                user_id=user_id,
                user_input=user_text,
                ai_response=ai_response,
                conversation_history=None
            )

            print(f"已添加对话: {user_text[:50]}...")

        print("所有对话数据已成功导入到记忆数据库")

    except Exception as e:
        print(f"导入对话数据时发生错误: {e}")

# 运行异步函数
if __name__ == "__main__":
    asyncio.run(import_dialogues_to_memory())