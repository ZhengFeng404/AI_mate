import edge_tts
import asyncio
import os


async def generate_tts(text, output_path):
    try:
        tts = edge_tts.Communicate(text, voice="zh-CN-XiaoyiNeural")
        await tts.save(output_path)

        if not os.path.exists(output_path):
            raise FileNotFoundError("TTS文件生成失败")

        return True
    except Exception as e:
        print(f"TTS生成失败: {str(e)}")
        return False

