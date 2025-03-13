# tts_handler.py
import os
import re
import hashlib
from pathlib import Path
import aiohttp
import edge_tts


class TTSGenerator:
    def __init__(self, cache_dir="tts_cache", ref_audio="还有，长生。她的鼻子，比狗狗灵.wav"):
        self.cache_dir = Path(cache_dir)
        self.ref_audio = ref_audio
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate_cache_name(self, text, prefix=None):
        """生成带哈希的缓存文件名"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        if prefix:
            return self.cache_dir / f"{prefix}_{text_hash}.wav"
        return self.cache_dir / f"tts_{text_hash}.wav"

    async def generate_tts(self, text, voice="zh-CN-XiaoyiNeural"):
        """Edge-TTS生成器"""
        clean_text = self._clean_text(text)
        output_path = self.generate_cache_name(clean_text, "edge")

        if output_path.exists():
            return str(output_path)

        try:
            tts = edge_tts.Communicate(clean_text, voice=voice)
            await tts.save(str(output_path))
            return str(output_path)
        except Exception as e:
            print(f"Edge-TTS生成失败: {e}")
            return None

    async def generate_gpt_sovits(self, text, prompt_text=None):
        """GPT-SoVITS生成器"""
        clean_text = self._clean_text(text)
        output_path = self.generate_cache_name(clean_text, "sovits")

        if output_path.exists():
            return str(output_path)

        params = {
            "text": clean_text,
            "text_lang": "zh",
            "ref_audio_path": str(self.ref_audio),
            "prompt_lang": "zh",
            "prompt_text": prompt_text or "还有，长生。她的鼻子，比狗狗灵"
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                async with session.get(
                        "http://127.0.0.1:9880/tts",
                        params=params
                ) as response:
                    if response.status == 200:
                        with open(output_path, "wb") as f:
                            f.write(await response.read())
                        return str(output_path)
                    print(f"GPT-SoVITS API错误: {response.status}")
                    return None
        except Exception as e:
            print(f"GPT-SoVITS请求失败: {e}")
            return None

    def _clean_text(self, text):
        """统一文本清理"""
        return re.sub(r"\[.*?\]|```", "", text).strip()