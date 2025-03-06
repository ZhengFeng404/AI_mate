from mem0 import Memory
import os
from utils.utils import load_api_key

GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "test_memory_ge",
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 768,
        }
    },
    "llm": { # LLM 配置在这里其实用不到，但为了完整性可以保留
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
            "model": "models/text-embedding-004",
        }
    }
}
m = Memory.from_config(config)

# 添加一些测试记忆 (使用与您的记忆库相似的数据)
#m.add("今天是晴天", user_id="test_user", metadata={"category": "weather"})
#m.add("我喜欢吃苹果", user_id="test_user", metadata={"category": "preferences"})
#m.add("我的名字是向日葵", user_id="test_user", metadata={"category": "identity"})


# 测试 query 1
query1 = "今天天气如何？"
related_memories_query1 = m.search(query=query1, user_id="test_user", limit=3)
print(f"Query 1: '{query1}'")
for entry in related_memories_query1:
    print(f"  Memory: {entry['memory']}, Score: {entry['score']}")

print("\n" + "="*30 + "\n") # 分隔线

