# memory_app.py
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from mid_term_memory_handler import add_to_mem0  # 假设这些 handler 位于 memory_handlers 目录下
from long_term_memory_handler import long_term_memory_async # 假设这些 handler 位于 memory_handlers 目录下
import logging
from pydantic import BaseModel
from datetime import datetime
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("memory_app")

memory_app = FastAPI()

last_two_long_term_memories = []

class MidTermMemoryRequest(BaseModel):
    user_id: str
    user_text: str
    response_text: str

class LongTermMemoryRequest(BaseModel):
    user_text: str
    response_text: str
    conversation_history_text: str

@memory_app.post("/mid_term_memory")
async def mid_term_memory_endpoint(request: MidTermMemoryRequest):
    try:
        await add_to_mem0(request.user_id, request.user_text, request.response_text)
        return JSONResponse({"status": "success", "message": "短期记忆存储成功"})
    except Exception as e:
        logger.error(f"短期记忆存储失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@memory_app.post("/long_term_memory")
async def long_term_memory_endpoint(request: LongTermMemoryRequest):
    try:
        memory_data = {
            "user_text": request.user_text,
            "response_text": request.response_text,
            "conversation_history_text": request.conversation_history_text,
            "timestamp": datetime.now().isoformat()
        }

        last_two_long_term_memories.append(memory_data)
        if len(last_two_long_term_memories) > 2:
            last_two_long_term_memories.pop(0)

        asyncio.create_task(
            long_term_memory_async(
                request.user_text,
                request.response_text,
                request.conversation_history_text,
                last_two_long_term_memories=last_two_long_term_memories
            )
        )
        return JSONResponse({"status": "success", "message": "长期记忆存储任务已启动, 并保存了记忆快照"})
    except Exception as e:
        logger.error(f"长期记忆存储任务启动失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(memory_app, host="0.0.0.0", port=5001) # Memory App 运行在 5001 端口