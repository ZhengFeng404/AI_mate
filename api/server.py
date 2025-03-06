# llm_tts_app.py (修改后的 app.py)
import asyncio
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from llm_handler import llm_response_generation # 导入 create_chat_session
from tts import generate_tts  # 这是 async 函数
import os
import json
from dotenv import load_dotenv
from datetime import datetime
import sys
import io
import time
from pydantic import BaseModel
from typing import Optional
import camera
import logging
import httpx # 导入 httpx 用于发送 HTTP 请求

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("uvicorn")

load_dotenv()
app = FastAPI()
AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

async def generate_tts_async(text, output_path):
    await generate_tts(text, output_path)

class chatRequest(BaseModel):
    text: str
    user_id: str = "default_user"
    image_base64: Optional[str] = None

user_chat_sessions = {}

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

camera_instance = None

@app.on_event("startup")
async def startup_event():
    global camera_instance
    camera_instance = camera.initialize_camera()
    if camera_instance is None:
        print("摄像头初始化失败，图像功能可能无法使用。")
    else:
        print("摄像头初始化成功。")

@app.on_event("shutdown")
async def shutdown_event():
    global camera_instance
    if camera_instance:
        camera.release_camera(camera_instance)
        print("摄像头资源已释放。")

MEMORY_APP_URL = "http://localhost:5001" # Memory App 的地址，根据实际情况修改

@app.post('/chat')
async def chat_endpoint(request: Request):
    logger.info("Received chat request")
    start_time_endpoint = time.time()
    try:
        data = await request.json()
        logger.debug(f"Received data: {data}")
        user_text = data.get('user_input')
        user_id = data.get('user_id', 'default_user')
        image_base64_uploaded = data.get('image_base64')

        image_base64_camera = None
        capture_camera_image = True
        if capture_camera_image and camera_instance:
            start_time_camera = time.time()
            image_base64_camera = camera.capture_and_encode_image(camera_instance)
            end_time_camera = time.time()
            camera_duration = end_time_camera - start_time_camera
            print(f"[Timing] Camera Capture + Encode Time: {camera_duration:.4f} seconds", flush=True)
        else:
            print("摄像头未初始化，无法捕获图像。")

        final_image_base64 = image_base64_uploaded if image_base64_uploaded else image_base64_camera

        # --- 手动维护对话历史 ---
        manual_history = user_chat_sessions.get(user_id, []) # 获取用户的历史记录，没有则创建空列表

        start_time_gemini = time.time()
        llm_response = llm_response_generation(user_text, user_id, user_chat_sessions, manual_history, # 传递 manual_history
                                               image_base64=final_image_base64)
        end_time_gemini = time.time()
        gemini_duration = end_time_gemini - start_time_gemini
        print(f"[Timing] Gemini Processing Time: {gemini_duration:.4f} seconds", flush=True)
        print(llm_response['response_text'])

        # 将用户输入添加到历史记录 (可以根据需要格式化历史记录条目)
        manual_history.append(f"User {user_id}: {user_text}")  # 简单的文本格式历史记录
        # 将 AI 回复添加到历史记录 (从 JSON 提取 response_text)
        ai_response_text = llm_response['response_text']
        manual_history.append(f"AI: {ai_response_text}") # 简单的文本格式历史记录

        user_chat_sessions[user_id] = manual_history # 更新 user_chat_sessions 中的历史记录

        start_time_parallel = time.time()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        audio_filename = f"output_{timestamp}.mp3"
        audio_path = os.path.abspath(os.path.join(AUDIO_DIR, audio_filename)).replace("\\", "/")
        audio_url = f"file:///{audio_path}"

        tts_task = generate_tts_async(llm_response['response_text'], audio_path)
        await tts_task
        end_time_parallel = time.time()
        parallel_duration = end_time_parallel - start_time_parallel
        print(f"[Timing] TTS Time: {parallel_duration:.4f} seconds", flush=True)

        print(f"[History]: {manual_history}", flush=True)
        #  异步发送记忆存储请求到 Memory App (不再等待)
        async def send_memory_requests():  # 定义一个异步函数来发送记忆请求
            try:
                async with httpx.AsyncClient() as client:
                    # 短期记忆
                    mid_term_memory_payload = {
                        "user_id": user_id,
                        "user_text": user_text,
                        "response_text": llm_response['response_text']
                    }
                    #await client.post(  # 注意这里仍然使用 await，但在 asyncio.create_task 中执行，不会阻塞主线程
                    #    f"{MEMORY_APP_URL}/mid_term_memory", json=mid_term_memory_payload)

                    # 长期记忆
                    long_term_memory_payload = {
                        "user_text": user_text,
                        "response_text": llm_response['response_text'],
                        "conversation_history_text": "\n".join(manual_history)
                    }
                    await client.post(  # 注意这里仍然使用 await，但在 asyncio.create_task 中执行，不会阻塞主线程
                        f"{MEMORY_APP_URL}/long_term_memory", json=long_term_memory_payload
                    )
                    print("[Timing] Memory Storage Requests Sent to Memory App in Background")

            except httpx.HTTPError as e:
                print(f"[Error] Failed to send memory storage request to Memory App in Background: {e}")

        asyncio.create_task(send_memory_requests())  # 创建后台任务，异步执行记忆存储请求
        print("[Timing] Memory Storage Task Started in Background (Non-blocking)")


        end_time_endpoint = time.time()
        endpoint_duration = end_time_endpoint - start_time_endpoint
        print(f"[Timing] Total Endpoint Time: {endpoint_duration:.4f} seconds", flush=True)

        return JSONResponse({
            "expression": llm_response['expression'],
            "motion": llm_response['motion'],
            "audio": audio_url,
            "response_text": llm_response['response_text']
        })

    except Exception as e:
        end_time_endpoint_error = time.time()
        endpoint_duration_error = end_time_endpoint_error - start_time_endpoint
        print(f"[Timing] Total Endpoint Time (Error): {endpoint_duration_error:.4f} seconds")
        print(f"[Error] Exception in chat_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        logger.error(f"Error in endpoint: {str(e)}", exc_info=True)

    finally:
        logger.info("Request processing completed")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000) # LLM+TTS App 运行在 5000 端口