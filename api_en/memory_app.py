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

last_two_long_term_memories_declarative = []
last_two_long_term_memories_complex = []

class MidTermMemoryRequest(BaseModel):
    user_id: str
    user_text: str
    response_text: str
    conversation_history_text: str

class LongTermMemoryRequest(BaseModel):
    user_id: str
    user_text: str
    response_text: str
    conversation_history_text: str

@memory_app.post("/mid_term_memory")
async def mid_term_memory_endpoint(request: MidTermMemoryRequest):
    try:
        await add_to_mem0(request.user_id, request.user_text, request.response_text, request.conversation_history_text)
        return JSONResponse({"status": "success", "message": "短期记忆存储成功"})
    except Exception as e:
        logger.error(f"短期记忆存储失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@memory_app.post("/long_term_memory_declarative")
async def long_term_memory_endpoint_declarative(request: LongTermMemoryRequest):
    try:
        memory_data = {
            "user_id": request.user_id,
            "user_input": request.user_text,
            "ai_response": request.response_text,
            "conversation_history_text": request.conversation_history_text,
            "timestamp": datetime.now().isoformat()
        }

        last_two_long_term_memories_declarative.append(memory_data)
        if len(last_two_long_term_memories_declarative) > 2:
            last_two_long_term_memories_declarative.pop(0)

        asyncio.create_task(
            long_term_memory_async(
                user_id=request.user_id,
                user_input=request.user_text,
                ai_response=request.response_text,
                conversation_history=request.conversation_history_text,
                memory_type="declarative",
                last_two_long_term_memories=last_two_long_term_memories_declarative
            )
        )
        return JSONResponse({"status": "success", "message": "declarative长期记忆存储任务已启动, 并保存了记忆快照"})
    except Exception as e:
        logger.error(f"declarative长期记忆存储任务启动失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@memory_app.post("/long_term_memory_complex")
async def long_term_memory_endpoint_complex(request: LongTermMemoryRequest):
    try:
        memory_data = {
            "user_id": request.user_id,
            "user_input": request.user_text,
            "ai_response": request.response_text,
            "conversation_history_text": request.conversation_history_text,
            "timestamp": datetime.now().isoformat()
        }

        last_two_long_term_memories_complex.append(memory_data)
        if len(last_two_long_term_memories_complex) > 2:
            last_two_long_term_memories_complex.pop(0)

        asyncio.create_task(
            long_term_memory_async(
                user_id=request.user_id,
                user_input=request.user_text,
                ai_response=request.response_text,
                conversation_history=request.conversation_history_text,
                memory_type="complex",
                last_two_long_term_memories=last_two_long_term_memories_complex
            )
        )
        return JSONResponse({"status": "success", "message": "complex长期记忆存储任务已启动, 并保存了记忆快照"})
    except Exception as e:
        logger.error(f"complex长期记忆存储任务启动失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(memory_app, host="0.0.0.0", port=5001) # Memory App 运行在 5001 端口