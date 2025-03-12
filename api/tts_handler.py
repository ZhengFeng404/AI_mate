#tts_handler.py
import edge_tts
import asyncio
import os
from io import BytesIO
import re
import requests

async def generate_tts(text, output_path):
    try:
        # 清理特殊符号
        clean_text = text.replace("```", "").strip()
        if not clean_text:
            raise ValueError("空文本内容")
        tts = edge_tts.Communicate(clean_text, voice="zh-CN-XiaoyiNeural")
        await tts.save(output_path)

        if not os.path.exists(output_path):
            raise FileNotFoundError("TTS文件生成失败")

        return True
    except Exception as e:
        print(f"TTS生成失败: {str(e)}")
        return False


# GPT-SoVits
async def generate_tts_GS(self, text, file_name_no_ext=None):
        file_name = self.generate_cache_file_name(file_name_no_ext, self.media_type)
        clean_text = text.replace("```", "").strip()
        cleaned_text = re.sub(r"\[.*?\]", "", clean_text)
        # Prepare the data for the POST request
        data = {
            "text": cleaned_text,
            "text_lang": "zh",
            "ref_audio_path": "それはそうかもだけど、こういうのって人からもらった方が嬉しくないあ.wav",
            "prompt_lang": "ja",
            "prompt_text": "それはそうかもだけど、こういうのって人からもらった方が嬉しくないあ",
            #"text_split_method": self.text_split_method,
            #"batch_size": self.batch_size,
            #"media_type": self.media_type,
            #"streaming_mode": self.streaming_mode,
        }

        # Send POST request to the TTS API
        response = requests.get("http://127.0.0.1:9880/tts", params=data, timeout=120)

        # Check if the request was successful
        if response.status_code == 200:
            # Save the audio content to a file
            with open(file_name, "wb") as audio_file:
                audio_file.write(response.content)
            return file_name
        else:
            # Handle errors or unsuccessful requests
            print(
                f"Error: Failed to generate audio. Status code: {response.status_code}"
            )
            return None

