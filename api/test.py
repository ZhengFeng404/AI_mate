import os
from mem0 import Memory
from utils.utils import load_api_key

GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

config = {
    "vector_store": {
        "provider": "qdrant",
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

m = Memory.from_config(config)
#all_memories = m.get_all(user_id="default_user")
#print(all_memories)

related_memories = m.search(query="阿姆斯特丹", user_id="default_user", limit=20)
print(related_memories)