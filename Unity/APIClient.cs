using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using Newtonsoft.Json.Linq;

namespace AI_Mate
{
    public class APIClient : MonoBehaviour
    {
        [Header("API 配置")]
        public string apiEndpoint = "https://15d7-80-112-169-174.ngrok-free.app/chat";
        public string apiKey = "";
        public string voiceRecognitionEndpoint = "https://15d7-80-112-169-174.ngrok-free.app/voice_recognition";

        private Action<string> onErrorCallback;
        private Action<AIMessage> onMessageCallback;

        public void Initialize(Action<AIMessage> messageCallback, Action<string> errorCallback)
        {
            onMessageCallback = messageCallback;
            onErrorCallback = errorCallback;
        }

        public IEnumerator SendChatRequest(string userText, string userId)
        {
            JObject requestData = new JObject();
            requestData["user_input"] = userText;
            requestData["user_id"] = userId;

            using (UnityWebRequest request = new UnityWebRequest(apiEndpoint, "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(requestData.ToString()));
                var downloadHandler = new StreamingDownloadHandler();
                request.downloadHandler = downloadHandler;
                request.SetRequestHeader("Content-Type", "application/json");
                if(!string.IsNullOrEmpty(apiKey)){
                    request.SetRequestHeader("Authorization", $"Bearer {apiKey}");
                }

                // 异步发送请求
                var operation = request.SendWebRequest();
                StringBuilder buffer = new StringBuilder();

                // 实时接收数据
                while (!operation.isDone)
                {
                    byte[] chunk = downloadHandler.GetBuffer();
                    if (chunk.Length > 0)
                    {
                        string chunkStr = Encoding.UTF8.GetString(chunk);
                        buffer.Append(chunkStr);

                        // 处理完整消息
                        int lastNewLine = buffer.ToString().LastIndexOf('\n');
                        if (lastNewLine >= 0)
                        {
                            string completeData = buffer.ToString(0, lastNewLine);
                            buffer.Remove(0, lastNewLine + 1);

                            string[] jsonLines = completeData.Split('\n');
                            foreach (string line in jsonLines)
                            {
                                if (!string.IsNullOrEmpty(line))
                                {
                                    ProcessResponseLine(line.Trim(), userId);
                                }
                            }
                        }
                    }
                    yield return null;
                }

                // 处理剩余数据
                if (buffer.Length > 0)
                {
                    ProcessResponseLine(buffer.ToString(), userId);
                }

                // 错误处理
                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogError($"Request failed: {request.error}");
                    onErrorCallback?.Invoke($"网络错误: {request.error}");
                }
            }
        }

        void ProcessResponseLine(string line, string userId)
        {
            try
            {
                JObject json = JObject.Parse(line);
                bool isLast = json["is_last"]?.ToObject<bool>() ?? false;

                AIMessage msg = new AIMessage
                {
                    isAI = true,
                    userId = userId,
                    timestamp = DateTime.Now.ToString("HH:mm:ss"),
                    aiId = json["ai_id"]?.ToString() ?? "default_ai",
                    content = json["segment"].ToString(),
                    expression = json["expression"].ToString(),
                    motion = json["motion"].ToString(),
                    audioUrl = json["audio_url"]?.ToString(),
                    isLast = isLast
                };

                onMessageCallback?.Invoke(msg);
            }
            catch (Exception e)
            {
                Debug.LogError($"解析失败: {e.Message}\n内容: {line}");
            }
        }

        public IEnumerator SendVoiceRecognitionRequest(AudioClip clip, string userId)
        {
            if (clip == null)
            {
                onErrorCallback?.Invoke("没有有效的录音");
                yield break;
            }

            // 获取音频管理器组件
            AudioManager audioManager = GetComponent<AudioManager>();
            if (audioManager == null)
            {
                audioManager = gameObject.AddComponent<AudioManager>();
            }

            // 将AudioClip转换为WAV格式
            byte[] wavData = audioManager.AudioClipToWav(clip);
            
            // 创建Web请求发送音频数据
            using (UnityWebRequest www = new UnityWebRequest(voiceRecognitionEndpoint, "POST"))
            {
                JObject requestData = new JObject();
                requestData["user_id"] = userId;
                requestData["audio_data"] = Convert.ToBase64String(wavData);
                
                www.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(requestData.ToString()));
                www.downloadHandler = new DownloadHandlerBuffer();
                www.SetRequestHeader("Content-Type", "application/json");
                
                yield return www.SendWebRequest();
                
                if (www.result == UnityWebRequest.Result.Success)
                {
                    // 处理语音识别结果
                    JObject response = JObject.Parse(www.downloadHandler.text);
                    string recognizedText = response["text"].ToString();
                    
                    if (!string.IsNullOrEmpty(recognizedText))
                    {
                        // 创建用户消息并通知回调
                        UserMessage userMsg = new UserMessage
                        {
                            timestamp = DateTime.Now.ToString("HH:mm:ss"),
                            userId = userId,
                            content = recognizedText
                        };
                        
                        // 这里我们需要特殊处理，因为onMessageCallback期望的是AIMessage
                        // 实际实现时可能需要另一个回调函数
                        yield return StartCoroutine(SendChatRequest(recognizedText, userId));
                    }
                }
                else
                {
                    Debug.LogError($"语音识别请求失败: {www.error}");
                    onErrorCallback?.Invoke($"语音识别失败: {www.error}");
                }
            }
        }
    }
} 