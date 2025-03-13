# llm_tts_app.py (修改后的 app.py)
import asyncio
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from llm_handler import llm_response_generation, get_gemini_response_with_history
#from tts_handler import generate_tts, generate_tts_GS  # 这是 async 函数
from history_manager import load_history, add_to_history
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
import uvicorn
import base64
import edge_tts
import google.generativeai as genai
from queue import Queue
import soundfile as sf
import numpy as np
import pygame
from tts_handler import TTSGenerator

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

# 初始化音频播放系统
pygame.mixer.init()
tts_queue = asyncio.Queue()
is_playing = False

class AudioBuffer:
    def __init__(self):
        self.buffer = []
        self.current_playing = None
        self.lock = asyncio.Lock()
        self.play_event = asyncio.Event()
        self.stop_flag = False

    async def add_audio(self, path):
        async with self.lock:
            if path is None:
                logger.error("尝试添加的音频路径为 None")
                return
            self.buffer.append(path)
            self.play_event.set()  # 触发播放循环

    async def play_loop(self):
        while not self.stop_flag:
            await self.play_event.wait()

            async with self.lock:
                if not self.buffer:
                    self.play_event.clear()
                    continue

                self.current_playing = self.buffer.pop(0)

            # 修改预加载逻辑
            def _preload_next():
                if len(self.buffer) > 0:
                    next_path = self.buffer[0]
                    try:
                        pygame.mixer.Sound(next_path)
                    except Exception as e:
                        logger.debug(f"预加载失败: {e}")

            # 正确使用 run_in_executor
            asyncio.get_event_loop().run_in_executor(None, _preload_next)  # 直接提交到线程池

            # 播放当前音频
            def _play():
                try:
                    pygame.mixer.init()
                    sound = pygame.mixer.Sound(self.current_playing)
                    sound.play()
                    while pygame.mixer.get_busy() and not self.stop_flag:
                        pygame.time.wait(100)
                    os.remove(self.current_playing)
                except Exception as e:
                    logger.error(f"播放失败: {e}")

            await asyncio.get_event_loop().run_in_executor(None, _play)  # 移除多余的create_task

    async def stop(self):
        self.stop_flag = True
        async with self.lock:
            for path in self.buffer:
                try:
                    os.remove(path)
                except:
                    pass
            self.buffer.clear()


# 初始化全局变量
audio_buffer = AudioBuffer()
tts_semaphore = asyncio.Semaphore(5)  # 并发控制

tts_engine = TTSGenerator(
    cache_dir="audio_cache",
)

async def tts_consumer():
    global tts_engine
    logger.info("TTS消费者启动")

    # 启动播放循环
    asyncio.create_task(audio_buffer.play_loop())

    while True:
        text_segment = await tts_queue.get()
        if text_segment is None:
            await audio_buffer.stop()
            break

        async with tts_semaphore:  # 并发控制
            try:
                #timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                #audio_path = os.path.join(AUDIO_DIR, f"temp_{timestamp}.wav")

                # 带超时控制的TTS生成
                try:
                    start_time = time.time()  # 记录 TTS 生成开始时间
                    audio_path = await tts_engine.generate_gpt_sovits(
                        text_segment,
                    )
                    end_time = time.time()    # 记录 TTS 生成结束时间
                    tts_duration = end_time - start_time # 计算 TTS 生成耗时

                    print(f"TTS生成耗时: {tts_duration:.4f} 秒, 文本: {text_segment}...") # 记录 TTS 耗时

                except asyncio.TimeoutError:
                    logger.warning(f"TTS生成超时: {text_segment[:20]}...")
                    continue

                await audio_buffer.add_audio(audio_path)
                logger.debug(f"已缓冲音频: {audio_path} (队列: {len(audio_buffer.buffer)})")

            except Exception as e:
                logger.error(f"处理失败: {e}")
                continue


def play_audio_sync(path):
    """同步播放音频（在子线程中运行）"""
    try:
        pygame.mixer.init()
        sound = pygame.mixer.Sound(path)
        logger.debug(f"开始播放音频: {path}")
        sound.play()
        while pygame.mixer.get_busy():
            pygame.time.wait(100)
        logger.debug(f"播放完成: {path}")
        os.remove(path)
    except Exception as e:
        logger.error(f"音频播放失败: {e}")

class chatRequest(BaseModel):
    text: str
    user_id: str = "default_user"
    image_base64: Optional[str] = None

user_chat_sessions = load_history()
user_conversation_turns = {}
camera_instance = None


@app.on_event("startup")
async def startup_event():
    global camera_instance, tts_consumer_task
    camera_instance = camera.initialize_camera()

    # 初始化音频系统
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)

    tts_consumer_task = asyncio.create_task(tts_consumer())
    logger.info("服务启动完成")


@app.on_event("shutdown")
async def shutdown_event():
    global camera_instance, tts_consumer_task
    # 发送终止信号
    await tts_queue.put(None)
    await tts_consumer_task
    await audio_buffer.stop()
    pygame.mixer.quit()

    if camera_instance:
        camera.release_camera(camera_instance)
    print("摄像头资源已释放。")


async def async_queue_generator(queue):
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
        queue.task_done()

MEMORY_APP_URL = "http://localhost:5001" # Memory App 的地址，根据实际情况修改

if __name__ == '__main__':
    user_provided_id = input("请输入您的名字以用作 user_id (直接回车使用默认 'default_user'): ")  # 提示用户输入
    if user_provided_id.strip():  # 检查用户是否输入了有效字符，strip()去除首尾空格
        user_id_to_use = user_provided_id.strip()  # 使用用户输入的名字
        print(f"User ID 将设置为: {user_id_to_use}")
    else:
        user_id_to_use = "default_user"  # 如果用户直接回车，则使用默认 user_id
        print(f"User ID 将设置为默认值: {user_id_to_use}")


    @app.post('/chat')
    async def chat_endpoint(request: Request):
        try:
            # 先解析请求数据 --------------------------------------------------
            data = await request.json()
            user_text = data.get('user_input')
            user_id = data.get('user_id', "default_user")
            image_base64_uploaded = data.get('image_base64')

            # 处理图像捕获逻辑 (保持原有代码不变) --------------------------------
            image_base64_camera = None
            if camera_instance:
                image_base64_camera = camera.capture_and_encode_image(camera_instance)
            final_image_base64 = image_base64_uploaded or image_base64_camera

            # 获取历史记录 ----------------------------------------------------
            manual_history = user_chat_sessions.get(user_id, [])

            # 创建流式生成器 --------------------------------------------------
            async def generate_stream():
                try:
                    llm_generator = get_gemini_response_with_history(
                        user_text,
                        user_id,
                        manual_history,
                        image_base64=final_image_base64
                    )

                    async for chunk in llm_generator:

                        print(f"🟠 Yielding chunk: {chunk}")  # 流输出调试
                        yield json.dumps(chunk) + "\n"
                        if chunk["type"] == "segment":
                            if chunk["segment"] == "```":
                                continue
                            else:
                                yield json.dumps({
                                "type": "segment",
                                "segment": chunk["segment"],
                                "expression": chunk["expression"],
                                "motion": chunk["motion"]
                                }) + "\n"
                                while tts_queue.qsize() > 5:
                                    await asyncio.sleep(0.5)
                                # 非阻塞放入 TTS 队列
                                asyncio.create_task(tts_queue.put(chunk["segment"]))

                        elif chunk["type"] == "complete":
                            yield json.dumps({
                                "type": "complete",
                                "full_text": chunk["result"]["response_text"]
                            }) + "\n"

                except Exception as e:
                    logger.error(f"Stream error: {e}")

            return StreamingResponse(generate_stream(), media_type="text/event-stream")

        except Exception as e:
            logger.error(f"Endpoint error: {e}")
            raise HTTPException(status_code=500, detail=str(e))



    uvicorn.run(app, host="0.0.0.0", port=5000) # LLM+TTS App 运行在 5000 端口

