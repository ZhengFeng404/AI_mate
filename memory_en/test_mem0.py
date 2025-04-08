import os
from mem0 import Memory
from utils.utils import load_api_key

GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "experiment_en",
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 3072,
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

m = Memory.from_config(config)
#all_memories = m.get_all(user_id="Alex")
#print(all_memories)

m.reset()
m.delete_all(user_id="艾利克斯")


related_memories = m.search(query="gym", user_id="Alex", limit=6)
print(related_memories)