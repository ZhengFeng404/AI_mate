# AI_mate
## How to run it for experiments
1. Docker running image for ollama, qdrant, weaviate
2. conda activate mate2
3. navigate to D:\AI\models\GPT-SoVITS-v3\GPT-SoVITS-v3lora-20250228
4. runtime/python.exe api_v2.py
5. navigate to memory/memory_en, rebuild both memory databases
6. better to delete qdrant image on Docker first
7. navigate to api/api_en, run any server____ script. run memeory_app.py

## How to connect to server with Unity Programme
1. navigate to D:\AI\ngrok-v3-stable-windows-amd64, run ngrok.exe
2. in the poped cmd, enter ngrok http --url=picked-evidently-mantis.ngrok-free.app 5000
3. navigate to C:\Users\fengz\Downloads\live2D_AI_mate, run live2D_mate.exe
4. this unity programme can be "Build and run" from Unity.