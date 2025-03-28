import requests

# 使用默认参数
response = requests.post("http://localhost:5000/record-and-transcribe")

# 或者自定义参数
response = requests.post(
    "http://localhost:5000/record-and-transcribe",
    params={
        "silence_threshold": 30,
        "silence_duration": 1.0,
        "sample_rate": 16000,
        "channels": 1
    }
)
result = response.json()
print("识别出的文本:", result.get("response_text"))