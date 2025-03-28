using UnityEngine;
using UnityEngine.UI;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework.Expression;
using Live2D.Cubism.Framework.Motion;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.IO;
using System.Net;
using UnityEngine.Networking;
using Newtonsoft.Json.Linq;
using TMPro;


[System.Serializable]
public class MotionClip
{
    public string name;
    public AnimationClip clip;
}

public struct UserMessage
{
    public string timestamp;
    public string userId;
    public string content;
}

public struct AIMessage
{
    public string timestamp;
    public string aiId;
    public string content;
    public string expression;
    public string motion;
    public string audioUrl;
    public bool isAI;
    public string userId;
    public bool isLast;
}

public class ChatEntry
{
    public string timestamp;
    public string displayName;
    public string content;
    public bool isAI;
    public bool isComplete;
}

public class StreamingDownloadHandler : DownloadHandlerScript
{
    private List<byte> buffer = new List<byte>();

    public StreamingDownloadHandler() : base(new byte[4096]) { }

    protected override bool ReceiveData(byte[] data, int dataLength)
    {
        if (data == null || dataLength == 0) return false;
        lock (buffer)
        {
            buffer.AddRange(data.Take(dataLength));
        }
        return true;
    }

    public byte[] GetBuffer()
    {
        lock (buffer)
        {
            byte[] result = buffer.ToArray();
            buffer.Clear();
            return result;
        }
    }
}

public class Live2DController : MonoBehaviour
{

    [Header("用户ID界面")]
    public GameObject idPanel;
    public TMP_InputField idInputField;
    public Button confirmIdButton;
    public TextMeshProUGUI currentIdDisplay;

    // Live2D组件
    public CubismModel model;
    public CubismExpressionController expressionController;
    public CubismMotionController motionController;
    public MotionClip[] motionClips;

    // UI组件
    public TMP_InputField chatInput;
    public Button sendButton;
    public TextMeshProUGUI chatContent; // 绑定到 ChatContent
    public ScrollRect chatScrollRect; // 绑定到 ChatHistoryPanel 的 ScrollRect

    // 语音识别相关组件
    [Header("语音识别")]
    public Button voiceRecognitionToggleButton;
    public TextMeshProUGUI voiceButtonText;
    public Image voiceButtonImage;
    public Sprite micOnSprite;
    public Sprite micOffSprite;
    public GameObject voiceIndicator; // 可选：语音识别指示器
    
    private bool isVoiceRecognitionActive = false;
    private string voiceRecognitionEndpoint = "http://127.0.0.1:5000/voice_recognition";
    private AudioClip recordedClip;
    private bool isRecording = false;

    public string currentUserID = "guest";

    [Header("API 配置")]
    public string apiEndpoint = "http://127.0.0.1:5000/chat"; // 新增字段
    public string apiKey = "";

    public class ChatRequest
    {
        public string user_input;
        public string user_id;
        public string image_base64;
    }

    public void UpdateUserID(string newUserID)
    {
        currentUserID = newUserID;
    }

    // 对话记录
    // private List<string> chatHistory = new List<string>();
    private List<ChatEntry> chatHistory = new List<ChatEntry>();

    // 控制参数
    private bool isWaitingResponse = false;
    private const float RequestCooldown = 1f;
    // private const string ApiUrl = "http://127.0.0.1:5000/chat";

    private Queue<string> audioQueue = new Queue<string>();
    private Queue<object> messageQueue = new Queue<object>();
    private bool isProcessingSegment = false;
    private bool isPlayingAudio = false;
    private string currentAITimestamp = null;
    private bool expectingNewAIReply = true;
    private bool isNewDialogueRound = true;

    // 添加新的成员变量
    private bool continuousListeningMode = true; // 启用连续监听模式
    private float segmentMaxDuration = 15.0f;    // 每段最大时长15秒
    private float silenceThresholdForSend = 1.0f; // 调整为1秒静音后自动发送
    private bool isProcessingAudioSegment = false; // 是否正在处理音频段
    private bool isTTSPlaying = false; // 控制TTS播放状态

private static readonly Color[] aiColors = new Color[]
{
    new Color(0.2f, 0.4f, 0.7f), // 蓝色
    new Color(0.7f, 0.2f, 0.4f)  // 红色
};

string GetDisplayColor(string aiId)
{
    int hash = aiId.GetHashCode();
    return ColorUtility.ToHtmlStringRGB(aiColors[Math.Abs(hash) % aiColors.Length]);
}

void EnqueueSegment(JObject json)
{
    if (json == null) return;

    // 添加字段存在性检查
    if (!json.ContainsKey("audio_url"))
    {
        Debug.LogError("Missing audio_url in response");
        return;
    }

    bool isAI = json.ContainsKey("ai_id");
    string displayId = isAI ?
        json["ai_id"].ToString() :
        json["user_id"].ToString();

    messageQueue.Enqueue(new AIMessage
    {
        isAI = true,
        userId = currentUserID,
        timestamp = DateTime.Now.ToString("HH:mm:ss"),
        aiId = json["ai_id"]?.ToString() ?? "default_ai",
        content = json["segment"].ToString(),
        expression = json["expression"].ToString(),
        motion = json["motion"].ToString(),
        audioUrl = json["audio_url"]?.ToString()
    });



    string audioUrlValue = json["audio_url"]?.ToString();
    if (!string.IsNullOrEmpty(audioUrlValue))
    {
        audioQueue.Enqueue(audioUrlValue);
    }

    if (!isProcessingSegment)
        StartCoroutine(ProcessMessageQueue());
}

IEnumerator ProcessMessageQueue()
{
    isProcessingSegment = true;
    while (messageQueue.Count > 0)
    {
        object msg = messageQueue.Dequeue();

        if(msg is UserMessage userMsg)
        {
            HandleUserMessage(userMsg);
            // 清除之前的未完成AI消息
            var incomplete = chatHistory.Where(e => e.isAI && !e.isComplete).ToList();
            foreach(var entry in incomplete)
            {
                entry.isComplete = true;
            }
        }
        else if(msg is AIMessage aiMsg)
        {
            HandleAIMessage(aiMsg);
        }

        yield return new WaitForSeconds(0.05f); // 缩短等待时间
    }
    isProcessingSegment = false;
}

void HandleUserMessage(UserMessage msg)
{
    // 结束之前的AI回复（如果有未完成的）
    var incompleteAI = chatHistory.LastOrDefault(e => e.isAI && !e.isComplete);
    if (incompleteAI != null)
    {
        incompleteAI.isComplete = true;
    }

    chatHistory.Add(new ChatEntry
    {
        timestamp = msg.timestamp,
        displayName = $"<color=green>{msg.userId}</color>",
        content = msg.content,
        isAI = false,
        isComplete = true
    });

    // 强制要求新的AI回复
    expectingNewAIReply = true;
    UpdateChatUI();
}

void HandleAIMessage(AIMessage msg)
{
    // 判断是否需要创建新条目
    bool isNewDialogueRound = !chatHistory.Any(e => e.isAI && !e.isComplete);
    bool isFirstChunk = false;

    ChatEntry currentEntry = isNewDialogueRound ?
        null :
        chatHistory.LastOrDefault(e => e.isAI && !e.isComplete);

    if (currentEntry == null)
    {
        // 创建新对话轮次
        currentEntry = new ChatEntry {
            timestamp = msg.timestamp,
            displayName = $"<color=#{GetDisplayColor(msg.aiId)}>{msg.aiId}</color>",
            content = msg.content,
            isAI = true,
            isComplete = msg.isLast
        };
        chatHistory.Add(currentEntry);
        isFirstChunk = true; // 标记为首个块
    }
    else
    {
        // 追加到现有对话
        currentEntry.content += msg.content;
        currentEntry.isComplete = msg.isLast;
    }

    UpdateChatUI();

    if (!string.IsNullOrEmpty(msg.audioUrl))
        {
            audioQueue.Enqueue(msg.audioUrl);
        }
    // 仅处理首个块的逻辑
    if (isFirstChunk)
    {

        SetExpression(msg.expression);
        PlayMotion(msg.motion);
    }

    // 维持原有状态机不变
    if (msg.isLast)
    {
        expectingNewAIReply = true;
    }
}


// 修改音频播放逻辑
private IEnumerator AudioPlaybackCoordinator()
{
    while (true)
    {
        if (audioQueue.Count > 0 && !isPlayingAudio)
        {
            isPlayingAudio = true;
            isTTSPlaying = true; // 标记TTS正在播放
            string url = audioQueue.Dequeue();
            yield return StartCoroutine(PlayAudioCoroutine(url));
            isPlayingAudio = false;
            isTTSPlaying = false; // 标记TTS播放结束
            
            // 添加短暂延迟，确保麦克风不会立即捕获最后一点回声
            yield return new WaitForSeconds(0.3f);
        }
        yield return null;
    }
}


void AppendToChatHistory(AIMessage data)
{
    string timestamp = GetCorrectTimestamp(data.isAI);
    string displayName = data.isAI ?
        $"<color=#{GetDisplayColor(data.aiId)}>{data.aiId}</color>" :
        $"<color=green>{data.userId}</color>";

    chatHistory.Add(new ChatEntry
    {
    timestamp = timestamp,
    displayName = displayName,
    content = data.content,
    isAI = data.isAI,
    isComplete = true
    });

    UpdateChatUI();
}

string GetCorrectTimestamp(bool isAI)
{
    if (isAI)
    {
        // 查找最后一个AI消息的时间戳
        var lastAI = chatHistory.LastOrDefault(e => e.isAI);
        return lastAI != null ? lastAI.timestamp : DateTime.Now.ToString("HH:mm:ss");
    }
    return DateTime.Now.ToString("HH:mm:ss");
}


private IEnumerator LoadAndPlayAudioAsync(string url)
{
    using (UnityWebRequest www = UnityWebRequestMultimedia.GetAudioClip(url, AudioType.WAV))
    {
        yield return www.SendWebRequest();

        if (www.result == UnityWebRequest.Result.Success)
        {
            AudioClip clip = DownloadHandlerAudioClip.GetContent(www);
            GetComponent<AudioSource>().PlayOneShot(clip);
        }
    }
}

void AppendToChat(string text)
{
    if (chatHistory.Count > 0 &&
        chatHistory.Last().isAI &&
        !chatHistory.Last().isComplete)
    {
        // 追加到现有消息
        chatHistory.Last().content += text;
    }
    else
    {
        // 创建新消息
        chatHistory.Add(new ChatEntry {
            timestamp = DateTime.Now.ToString("HH:mm:ss"),
            displayName = "AI",
            content = text,
            isAI = true,
            isComplete = false
        });
    }
    UpdateChatUI();
}


    void Start()
    {
        sendButton.onClick.AddListener(OnSendButtonClick);
        // 初始化对话记录
        chatHistory.Clear();
        UpdateChatUI();
        StartCoroutine(AudioPlaybackCoordinator());

        // 设置语音识别按钮
        if (voiceRecognitionToggleButton != null)
        {
            voiceRecognitionToggleButton.onClick.AddListener(ToggleVoiceRecognition);
            UpdateVoiceButtonUI();
        }

        if(idInputField == null)
    {
        idInputField = GameObject.Find("IDInputField").GetComponent<TMP_InputField>();
    }
        // 初始化ID界面
        if(idPanel != null)
        {
        idPanel.SetActive(true); // 默认显示ID输入界面
        confirmIdButton.onClick.AddListener(OnConfirmID);
        }
        //ChatHistoryPanel.SetActive(false);
        //inputPanel.SetActive(false);

        // 加载保存的ID
        string savedId = PlayerPrefs.GetString("UserID");
        if(!string.IsNullOrEmpty(savedId)){
        idInputField.text = savedId;
        OnConfirmID(); // 自动应用已保存的ID
        }
    }

    void OnConfirmID()
    {
        string newId = idInputField.text.Trim();
        if(string.IsNullOrEmpty(newId)){
            newId = "guest_" + UnityEngine.Random.Range(1000,9999);
            idInputField.text = newId;
        }

        currentUserID = newId;
        currentIdDisplay.text = $"当前用户：{newId}";
        // idPanel.SetActive(false); // 隐藏ID输入面板

        // 保存到本地
        PlayerPrefs.SetString("UserID", newId);
        PlayerPrefs.Save();

        //ChatHistoryPanel.SetActive(true);
        //ChatInput.SetActive(true);
    }

    // 添加切换ID按钮功能
    public void ShowIdPanel()
{
    idPanel.SetActive(true);
    idInputField.text = currentUserID;
}



    // 添加对话记录
    void AddChatMessage(string userMessage, string responseMessage)
{
    string timestamp = DateTime.Now.ToString("HH:mm:ss");

    // 用户消息
    chatHistory.Add(new ChatEntry {
        timestamp = timestamp,
        displayName = "<color=green>你</color>",
        content = userMessage,
        isAI = false,
        isComplete = true
    });

    // AI回复
    chatHistory.Add(new ChatEntry {
        timestamp = timestamp,
        displayName = "<color=black>AI</color>",
        content = responseMessage,
        isAI = true,
        isComplete = true
    });

    UpdateChatUI();
}



    // 更新 UI 显示
    void UpdateChatUI()
{
    StringBuilder chatText = new StringBuilder();

    foreach (var entry in chatHistory)
    {
        string entryLine = $"[{entry.timestamp}] {entry.displayName}：{entry.content}";
        chatText.AppendLine(entryLine);
        chatText.AppendLine();
    }

    chatContent.text = chatText.ToString();

    // 保持自动滚动
    Canvas.ForceUpdateCanvases();
    chatContent.rectTransform.sizeDelta = new Vector2(
        chatContent.rectTransform.sizeDelta.x,
        chatContent.preferredHeight
    );
    chatScrollRect.verticalNormalizedPosition = 0f;
}

    void OnSendButtonClick()
{
    //if (!isWaitingResponse && !string.IsNullOrWhiteSpace(chatInput.text))
    if (!string.IsNullOrWhiteSpace(chatInput.text))
    {
        // 创建纯净用户消息
        UserMessage userMsg = new UserMessage{
            timestamp = DateTime.Now.ToString("HH:mm:ss"),
            userId = currentUserID,
            content = chatInput.text.Trim()
        };

        // 加入队列并立即显示
        messageQueue.Enqueue(userMsg);
        if (!isProcessingSegment)
            StartCoroutine(ProcessMessageQueue());

        // 发送请求
        StartCoroutine(SendRequestCoroutine(chatInput.text.Trim()));
        chatInput.text = "";
    }
}


    IEnumerator SendRequestCoroutine(string userText)
{
    isWaitingResponse = true;

    JObject requestData = new JObject();
    requestData["user_input"] = userText;
    requestData["user_id"] = currentUserID;

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
                            ProcessResponseLine(line.Trim());
                        }
                    }
                }
            }
            yield return null;
        }

        // 处理剩余数据
        if (buffer.Length > 0)
        {
            ProcessResponseLine(buffer.ToString());
        }

        // 错误处理
        if (request.result != UnityWebRequest.Result.Success)
        {
            Debug.LogError($"Request failed: {request.error}");
            EnqueueErrorMessage($"网络错误: {request.error}");
        }
    }

    isWaitingResponse = false;
}

void ProcessResponseLine(string line)
{
    try
    {
        JObject json = JObject.Parse(line);
        bool isLast = json["is_last"]?.ToObject<bool>() ?? false;

        AIMessage msg = new AIMessage
        {
            isAI = true,
            userId = currentUserID,
            timestamp = DateTime.Now.ToString("HH:mm:ss"),
            aiId = json["ai_id"]?.ToString() ?? "default_ai",
            content = json["segment"].ToString(),
            expression = json["expression"].ToString(),
            motion = json["motion"].ToString(),
            audioUrl = json["audio_url"]?.ToString(),
            isLast = isLast
        };

        messageQueue.Enqueue(msg);

        if (!isProcessingSegment)
            StartCoroutine(ProcessMessageQueue());
    }
    catch (Exception e)
    {
        Debug.LogError($"解析失败: {e.Message}\n内容: {line}");
    }
}

// 新增错误消息处理方法
void EnqueueErrorMessage(string message)
{
    UserMessage errorMsg = new UserMessage {
        timestamp = DateTime.Now.ToString("HH:mm:ss"),
        userId = "system",
        content = $"⚠️ {message}"
    };
    messageQueue.Enqueue(errorMsg);

    if (!isProcessingSegment) {
        StartCoroutine(ProcessMessageQueue());
    }
}

    void SetExpression(string expressionName)
    {
        if (expressionController == null || expressionController.ExpressionsList == null) return;

        for (int i = 0; i < expressionController.ExpressionsList.CubismExpressionObjects.Length; i++)
        {
            var expr = expressionController.ExpressionsList.CubismExpressionObjects[i];
            if (expr == null) continue;

            // 关键修改：去除后缀后匹配
            var exprName = expr.name.Replace(".exp3", "").Trim();
            if (exprName == expressionName)
            {
                expressionController.CurrentExpressionIndex = i;
                return;
            }
        }

        Debug.LogWarning($"Expression not found: {expressionName}");
    }

    void PlayMotion(string motionName)
{
    if (motionController == null) return;

    // 根据名称查找 AnimationClip
    AnimationClip clip = null;
    foreach (var motionClip in motionClips)
    {
        if (motionClip.name == motionName)
        {
            clip = motionClip.clip;
            break;
        }
    }

    if (clip != null)
    {
        // 调用内置方法，传入 AnimationClip 和优先级
        motionController.PlayAnimation(clip, priority: CubismMotionPriority.PriorityForce);
    }
    else
    {
        Debug.LogWarning("Animation clip not found: " + motionName);
    }
}

    void PlayAudio(string audioPath)
    {
    if (GetComponent<AudioSource>() == null)
    {
        Debug.LogError("AudioSource component is missing!");
        return;
    }
        StartCoroutine(PlayAudioCoroutine(audioPath));
    }

    private IEnumerator PlayAudioCoroutine(string url)
{
    using (UnityWebRequest www = UnityWebRequestMultimedia.GetAudioClip(url, AudioType.WAV))
    {
        yield return www.SendWebRequest();

        if (www.result == UnityWebRequest.Result.Success)
        {
            AudioClip clip = DownloadHandlerAudioClip.GetContent(www);
            AudioSource audioSource = GetComponent<AudioSource>();
            audioSource.clip = clip;
            audioSource.Play();

            // 等待音频播放完成
            while (audioSource.isPlaying)
            {
                yield return null;
            }
        }
        else
        {
            Debug.LogError($"音频加载失败: {www.error}");
        }
    }
}

    // 切换语音识别状态
    void ToggleVoiceRecognition()
    {
        isVoiceRecognitionActive = !isVoiceRecognitionActive;
        
        if (isVoiceRecognitionActive)
        {
            StartVoiceRecognition();
        }
        else
        {
            StopVoiceRecognition();
        }
        
        UpdateVoiceButtonUI();
    }
    
    // 更新语音按钮UI
    void UpdateVoiceButtonUI()
    {
        if (voiceButtonText != null)
        {
            if (continuousListeningMode && isVoiceRecognitionActive)
                voiceButtonText.text = "结束语音模式";
            else
                voiceButtonText.text = isVoiceRecognitionActive ? "停止语音" : "开始语音";
        }
        
        if (voiceButtonImage != null && micOnSprite != null && micOffSprite != null)
        {
            voiceButtonImage.sprite = isVoiceRecognitionActive ? micOnSprite : micOffSprite;
        }
        
        if (voiceIndicator != null)
        {
            voiceIndicator.SetActive(isVoiceRecognitionActive);
        }
    }
    
    // 开始语音识别
    void StartVoiceRecognition()
    {
        Debug.Log("开始语音识别");
        if (continuousListeningMode)
        {
            StartCoroutine(ContinuousListeningCoroutine());
        }
        else
        {
            StartCoroutine(VoiceRecognitionCoroutine());
        }
    }
    
    // 停止语音识别
    void StopVoiceRecognition()
    {
        Debug.Log("停止语音识别");
        isRecording = false;
        Microphone.End(null); // 停止所有麦克风录制
        
        if (recordedClip != null && !continuousListeningMode)
        {
            StartCoroutine(ProcessRecordedAudio(recordedClip));
        }
    }
    
    IEnumerator VoiceRecognitionCoroutine()
    {
        // 请求麦克风权限
        yield return Application.RequestUserAuthorization(UserAuthorization.Microphone);
        
        if (!Application.HasUserAuthorization(UserAuthorization.Microphone))
        {
            Debug.LogError("麦克风权限被拒绝");
            isVoiceRecognitionActive = false;
            UpdateVoiceButtonUI();
            yield break;
        }
        
        isRecording = true;
        
        // 创建更长的录音缓冲区（最多允许3分钟）
        recordedClip = Microphone.Start(null, true, 180, 44100);
        
        // 使用自适应VAD参数
        float recordingTime = 0;
        float initialSilenceTime = 1.5f; // 初始短静音检测
        float maxSilenceTime = 4.0f;     // 最大静音容忍
        float silenceIncreaseRate = 0.5f; // 每10秒增加静音容忍的速率
        float adaptiveSilenceTime = initialSilenceTime; // 动态调整的静音容忍时间
        
        float lastSoundTime = Time.time;
        bool silenceDetected = false;
        bool hasStartedSpeaking = false; // 是否已经开始说话
        float volumeThreshold = 0.02f;   // 默认音量阈值
        float peakVolume = 0;            // 记录峰值音量
        float averageVolume = 0;         // 平均音量
        int volumeSampleCount = 0;       // 采样计数
        
        // 音量历史记录，用于平滑判断
        List<float> volumeHistory = new List<float>();
        int historySize = 20; // 保留20帧的音量历史
        
        // 视觉反馈
        if (voiceIndicator != null)
        {
            StartCoroutine(PulseVoiceIndicator());
        }
        
        // 显示录音已开始的UI提示
        if (voiceButtonText != null)
        {
            voiceButtonText.text = "正在聆听...";
        }
        
        // 自动校准阶段
        Debug.Log("开始音量校准...");
        float calibrationTime = 1.0f; // 校准1秒
        float calibrationTimer = 0;
        float calibrationSum = 0;
        int calibrationSamples = 0;
        
        while (calibrationTimer < calibrationTime && isRecording)
        {
            calibrationTimer += Time.deltaTime;
            float volume = GetCurrentAudioLevel();
            calibrationSum += volume;
            calibrationSamples++;
            yield return null;
        }
        
        // 设置自适应阈值
        if (calibrationSamples > 0)
        {
            float avgBackgroundNoise = calibrationSum / calibrationSamples;
            volumeThreshold = Mathf.Max(0.02f, avgBackgroundNoise * 1.5f);
            Debug.Log($"背景噪音水平: {avgBackgroundNoise}, 设置阈值: {volumeThreshold}");
        }
        
        Debug.Log("开始录音...");
        
        while (isRecording && isVoiceRecognitionActive)
        {
            // 更新录音时间
            recordingTime += Time.deltaTime;
            
            // 获取当前音量
            float currentVolume = GetCurrentAudioLevel();
            
            // 更新音量历史
            volumeHistory.Add(currentVolume);
            if (volumeHistory.Count > historySize)
            {
                volumeHistory.RemoveAt(0);
            }
            
            // 计算短期平均音量(最近10帧)
            float recentAvgVolume = 0;
            int recentCount = Mathf.Min(10, volumeHistory.Count);
            for (int i = volumeHistory.Count - 1; i >= volumeHistory.Count - recentCount; i--)
            {
                recentAvgVolume += volumeHistory[i];
            }
            recentAvgVolume /= recentCount;
            
            // 更新音量统计
            if (currentVolume > peakVolume)
            {
                peakVolume = currentVolume;
            }
            
            volumeSampleCount++;
            averageVolume = ((averageVolume * (volumeSampleCount - 1)) + currentVolume) / volumeSampleCount;
            
            // 动态调整静音容忍时间
            // 随着录音时间增加，给予更长的静音容忍
            adaptiveSilenceTime = initialSilenceTime + (recordingTime / 10) * silenceIncreaseRate;
            adaptiveSilenceTime = Mathf.Min(adaptiveSilenceTime, maxSilenceTime); // 上限为最大容忍时间
            
            // 检测声音是否高于阈值
            if (currentVolume > volumeThreshold || recentAvgVolume > volumeThreshold * 0.8f)
            {
                if (!hasStartedSpeaking)
                {
                    Debug.Log("检测到用户开始说话");
                    hasStartedSpeaking = true;
                }
                
                lastSoundTime = Time.time;
                silenceDetected = false;
                
                // 可视化反馈音量
                UpdateVoiceIndicatorLevel(currentVolume);
            }
            else if (hasStartedSpeaking && Time.time - lastSoundTime > adaptiveSilenceTime && !silenceDetected)
            {
                // 用户开始说话后又检测到足够长的静音
                silenceDetected = true;
                Debug.Log($"检测到{adaptiveSilenceTime:0.1f}秒静音");
                
                // 显示倒计时
                StartCoroutine(ShowSilenceCountdown(2.0f)); // 2秒倒计时
            }
            
            // 语音终止条件:
            // 1. 用户已经说过话，并且静音超过阈值+缓冲
            bool terminateByLongSilence = hasStartedSpeaking && silenceDetected && 
                                         (Time.time - lastSoundTime) > (adaptiveSilenceTime + 2.0f);
            
            // 2. 录音时间过长(3分钟安全上限)
            bool terminateByMaxDuration = recordingTime > 180;
            
            // 3. 连续低音量一段时间(30秒)无有效语音，可能是环境噪音
            bool terminateByLowVolume = recordingTime > 30 && peakVolume < volumeThreshold * 2;
            
            if (terminateByLongSilence)
            {
                Debug.Log($"终止条件：静音超时（{Time.time - lastSoundTime:0.1f}秒）");
                break;
            }
            
            if (terminateByMaxDuration)
            {
                Debug.Log("终止条件：达到最大录音时间");
                break;
            }
            
            if (terminateByLowVolume && !hasStartedSpeaking)
            {
                Debug.Log("终止条件：长时间低音量，无有效语音");
                break;
            }
            
            // 提供视觉反馈
            if (voiceButtonText != null)
            {
                if (silenceDetected)
                {
                    float remainingTime = adaptiveSilenceTime + 2.0f - (Time.time - lastSoundTime);
                    if (remainingTime > 0)
                    {
                        voiceButtonText.text = $"即将完成... {remainingTime:0.1f}s";
                    }
                }
                else if (hasStartedSpeaking)
                {
                    voiceButtonText.text = "正在录音...";
                }
                else
                {
                    voiceButtonText.text = "请开始说话...";
                }
            }
            
            yield return null;
        }
        
        // 如果没检测到任何说话，可能是误触或环境噪音
        if (!hasStartedSpeaking || peakVolume < volumeThreshold * 1.5f)
        {
            Debug.Log("未检测到有效语音，取消处理");
            isRecording = false;
            Microphone.End(null);
            recordedClip = null; // 不处理录音
            
            if (voiceButtonText != null)
            {
                voiceButtonText.text = "未检测到语音";
                yield return new WaitForSeconds(1.0f);
                voiceButtonText.text = "开始语音";
            }
            
            isVoiceRecognitionActive = false;
            UpdateVoiceButtonUI();
            yield break;
        }
        
        Debug.Log($"录音完成。峰值音量: {peakVolume:0.000}, 平均音量: {averageVolume:0.000}, 时长: {recordingTime:0.0}秒");
        
        // 停止录音并处理
        StopVoiceRecognition();
    }
    
    // 获取当前音频级别（增强版）
    float GetCurrentAudioLevel()
    {
        if (!Microphone.IsRecording(null) || recordedClip == null)
            return 0;
            
        // 使用更大的采样窗口获得更稳定的音量
        float[] samples = new float[256];
        int position = Microphone.GetPosition(null);
        
        // 确保有足够的数据可读
        if (position < samples.Length)
            return 0;
            
        // 从当前位置向前读取样本
        recordedClip.GetData(samples, position - samples.Length);
        
        // 计算RMS音量
        float sum = 0;
        for (int i = 0; i < samples.Length; i++)
        {
            sum += samples[i] * samples[i];
        }
        
        // 应用非线性映射使小音量更敏感
        float rms = Mathf.Sqrt(sum / samples.Length);
        float nonLinearVolume = Mathf.Pow(rms, 0.8f); // 小音量时更敏感
        
        return nonLinearVolume;
    }
    
    // 语音指示器脉冲效果
    IEnumerator PulseVoiceIndicator()
    {
        if (voiceIndicator == null) yield break;
        
        Vector3 originalScale = voiceIndicator.transform.localScale;
        Color originalColor = voiceIndicator.GetComponent<Image>().color;
        
        while (isRecording && isVoiceRecognitionActive)
        {
            // 呼吸效果
            float pulse = 0.8f + 0.2f * Mathf.Sin(Time.time * 3f);
            voiceIndicator.transform.localScale = originalScale * pulse;
            
            yield return null;
        }
        
        // 重置到原始状态
        if (voiceIndicator != null)
        {
            voiceIndicator.transform.localScale = originalScale;
        }
    }
    
    // 显示静音倒计时
    IEnumerator ShowSilenceCountdown(float duration)
    {
        float countdownTime = duration;
        
        while (countdownTime > 0 && isRecording && isVoiceRecognitionActive)
        {
            countdownTime -= Time.deltaTime;
            
            if (voiceButtonText != null)
            {
                voiceButtonText.text = $"静音倒计时 {countdownTime:0.0}s";
            }
            
            yield return null;
        }
        
        if (voiceButtonText != null && isVoiceRecognitionActive)
        {
            voiceButtonText.text = "停止语音";
        }
    }
    
    // 更新语音指示器音量显示
    void UpdateVoiceIndicatorLevel(float volume)
    {
        if (voiceIndicator == null) return;
        
        // 根据音量调整指示器大小
        float scaleFactor = 1.0f + volume * 5.0f; // 放大效果
        scaleFactor = Mathf.Clamp(scaleFactor, 1.0f, 2.0f);
        
        // 应用新的缩放
        Vector3 baseScale = Vector3.one;
        voiceIndicator.transform.localScale = baseScale * scaleFactor;
        
        // 可选：根据音量改变颜色
        Image indicatorImage = voiceIndicator.GetComponent<Image>();
        if (indicatorImage != null)
        {
            // 音量越大颜色越鲜艳
            Color activeColor = new Color(0.2f, 0.8f, 0.2f, 0.8f + volume * 0.2f);
            indicatorImage.color = activeColor;
        }
    }

    // 添加回之前被删除的函数
    IEnumerator ProcessRecordedAudio(AudioClip clip)
    {
        // 将AudioClip转换为WAV格式
        byte[] wavData = AudioClipToWav(clip);
        
        // 创建Web请求发送音频数据
        using (UnityWebRequest www = new UnityWebRequest(voiceRecognitionEndpoint, "POST"))
        {
            JObject requestData = new JObject();
            requestData["user_id"] = currentUserID;
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
                    // 添加用户消息
                    UserMessage userMsg = new UserMessage
                    {
                        timestamp = DateTime.Now.ToString("HH:mm:ss"),
                        userId = currentUserID,
                        content = recognizedText
                    };
                    
                    messageQueue.Enqueue(userMsg);
                    if (!isProcessingSegment)
                        StartCoroutine(ProcessMessageQueue());
                    
                    // 发送给LLM
                    StartCoroutine(SendRequestCoroutine(recognizedText));
                }
            }
            else
            {
                Debug.LogError($"语音识别请求失败: {www.error}");
                EnqueueErrorMessage($"语音识别失败: {www.error}");
            }
        }
    }
    
    // 将AudioClip转换为WAV格式的字节数组
    byte[] AudioClipToWav(AudioClip clip)
    {
        if (clip == null) return new byte[0];
        
        float[] samples = new float[clip.samples * clip.channels];
        clip.GetData(samples, 0);
        
        // 将浮点数样本转换为16位PCM
        short[] intData = new short[samples.Length];
        for (int i = 0; i < samples.Length; i++)
        {
            intData[i] = (short)(samples[i] * 32767);
        }
        
        using (MemoryStream ms = new MemoryStream())
        {
            using (BinaryWriter writer = new BinaryWriter(ms))
            {
                // WAV文件头
                writer.Write(Encoding.ASCII.GetBytes("RIFF"));
                writer.Write(36 + intData.Length * 2);
                writer.Write(Encoding.ASCII.GetBytes("WAVE"));
                writer.Write(Encoding.ASCII.GetBytes("fmt "));
                writer.Write(16);
                writer.Write((short)1); // 音频格式，1表示PCM
                writer.Write((short)clip.channels);
                writer.Write(clip.frequency);
                writer.Write(clip.frequency * clip.channels * 2); // 字节率
                writer.Write((short)(clip.channels * 2)); // 块对齐
                writer.Write((short)16); // 位深度
                
                // 数据块
                writer.Write(Encoding.ASCII.GetBytes("data"));
                writer.Write(intData.Length * 2);
                
                // 将short数组转换为字节并写入
                foreach (short s in intData)
                {
                    writer.Write(s);
                }
            }
            return ms.ToArray();
        }
    }

    // 新增：添加一个结果类来替代out参数
    public class AudioSegmentResult
    {
        public bool hasValidSpeech;
        public AudioClip segment;
    }

    // 修改：使用返回值类代替out参数
    IEnumerator ContinuousListeningCoroutine()
    {
        // 请求麦克风权限
        yield return Application.RequestUserAuthorization(UserAuthorization.Microphone);
        
        if (!Application.HasUserAuthorization(UserAuthorization.Microphone))
        {
            Debug.LogError("麦克风权限被拒绝");
            isVoiceRecognitionActive = false;
            UpdateVoiceButtonUI();
            yield break;
        }

        // 校准环境噪音 - 修改为使用返回值
        float volumeThreshold = 0.02f;
        CalibrationResult calibResult = new CalibrationResult();
        yield return StartCoroutine(CalibrateNoise(calibResult));
        volumeThreshold = calibResult.threshold;
        
        Debug.Log($"开始连续监听模式，噪音阈值: {volumeThreshold}");
        
        if (voiceButtonText != null)
        {
            voiceButtonText.text = "聆听中...";
        }
        
        bool processingSegment = false; // 标记是否正在处理一个语音段
        float cooldownAfterTTS = 0f;    // TTS播放后的冷却时间
        
        // 开始连续监听循环
        while (isVoiceRecognitionActive)
        {
            // TTS播放状态检查
            if (isTTSPlaying)
            {
                if (voiceButtonText != null)
                {
                    voiceButtonText.text = "AI正在说话...";
                }
                cooldownAfterTTS = 0.5f; // 设置TTS结束后的冷却时间
                yield return new WaitForSeconds(0.1f);
                continue;
            }
            
            // TTS播放后的冷却期
            if (cooldownAfterTTS > 0)
            {
                cooldownAfterTTS -= Time.deltaTime;
                if (voiceButtonText != null)
                {
                    voiceButtonText.text = "等待中...";
                }
                yield return null;
                continue;
            }
            
            if (processingSegment)
            {
                // 如果正在处理，等待一小段时间
                yield return new WaitForSeconds(0.1f);
                continue;
            }
            
            processingSegment = true;
            
            // 修改：使用返回值而非out参数
            AudioSegmentResult result = new AudioSegmentResult();
            Debug.Log("开始获取新的音频段...");
            yield return StartCoroutine(RecordAudioSegment(volumeThreshold, result));
            
            // 如果有有效语音内容且不是正在处理中，发送到服务器
            if (result.hasValidSpeech && result.segment != null && !isProcessingAudioSegment)
            {
                isProcessingAudioSegment = true;
                // 显示识别中状态
                if (voiceButtonText != null)
                {
                    voiceButtonText.text = "识别中...";
                }
                
                // 处理录音片段
                Debug.Log("检测到有效语音段，立即发送处理...");
                yield return StartCoroutine(ProcessRecordedAudio(result.segment));
                isProcessingAudioSegment = false;
                
                // 恢复监听状态显示
                if (voiceButtonText != null && isVoiceRecognitionActive)
                {
                    voiceButtonText.text = "聆听中...";
                }
            }
            else
            {
                Debug.Log("未检测到有效语音，继续监听...");
            }
            
            processingSegment = false;
            
            // 很短的延迟，避免CPU占用过高，但不影响响应速度
            yield return new WaitForSeconds(0.05f);
        }
        
        Debug.Log("连续监听模式已结束");
    }

    // 修改：录制单个音频段 - 使用返回值类代替out参数
    IEnumerator RecordAudioSegment(float volumeThreshold, AudioSegmentResult result)
    {
        result.hasValidSpeech = false;
        result.segment = null;
        
        // 等待任何TTS播放完成
        while (isTTSPlaying)
        {
            yield return new WaitForSeconds(0.1f);
        }
        
        // 开始录制当前段
        AudioClip currentSegment = Microphone.Start(null, false, (int)segmentMaxDuration, 44100);
        
        float recordingTime = 0;
        bool hasStartedSpeaking = false;
        float lastSoundTime = Time.time;
        float peakVolume = 0;
        
        // 音量历史记录
        List<float> volumeHistory = new List<float>();
        int historySize = 10;
        
        // 噪音样本收集 - 用于动态调整阈值
        float[] noiseHistory = new float[5];
        int noiseIndex = 0;
        float noiseAverage = volumeThreshold;
        
        // 启动可视反馈
        if (voiceIndicator != null)
        {
            StartCoroutine(PulseVoiceIndicator());
        }
        
        // 调试信息
        Debug.Log("开始录制新的音频段，等待用户说话...");
        
        // 记录语音开始和结束时间点
        float speechStartSample = 0;
        float speechEndSample = 0;
        
        // 初始收集环境噪音阶段
        Debug.Log("正在收集环境噪音样本...");
        for (int i = 0; i < 10 && isVoiceRecognitionActive; i++)
        {
            float currentVolume = GetCurrentAudioLevelFrom(currentSegment);
            noiseHistory[noiseIndex] = currentVolume;
            noiseIndex = (noiseIndex + 1) % noiseHistory.Length;
            
            yield return new WaitForSeconds(0.1f);
        }
        
        // 计算噪音平均值并调整阈值
        float sum = 0;
        foreach (float noise in noiseHistory)
        {
            sum += noise;
        }
        noiseAverage = sum / noiseHistory.Length;
        float adjustedThreshold = Mathf.Max(volumeThreshold, noiseAverage * 2.0f);
        
        Debug.Log($"环境噪音水平: {noiseAverage:0.000}, 调整后的阈值: {adjustedThreshold:0.000}");
        
        while (recordingTime < segmentMaxDuration && isVoiceRecognitionActive)
        {
            // 检查TTS是否已开始播放 - 如果是，中断录音
            if (isTTSPlaying)
            {
                Debug.Log("检测到TTS播放，暂停语音识别");
                break;
            }
            
            recordingTime += Time.deltaTime;
            
            // 获取当前音量
            float currentVolume = GetCurrentAudioLevelFrom(currentSegment);
            
            // 更新音量历史
            volumeHistory.Add(currentVolume);
            if (volumeHistory.Count > historySize)
            {
                volumeHistory.RemoveAt(0);
            }
            
            // 计算短期平均音量 - 使用滑动窗口以降低单个峰值的影响
            float recentAvgVolume = 0;
            foreach (float vol in volumeHistory)
            {
                recentAvgVolume += vol;
            }
            recentAvgVolume /= volumeHistory.Count;
            
            // 更新峰值音量
            if (currentVolume > peakVolume)
            {
                peakVolume = currentVolume;
            }
            
            // 检测声音是否高于阈值 - 使用调整后的阈值
            if (currentVolume > adjustedThreshold * 1.2f || recentAvgVolume > adjustedThreshold)
            {
                if (!hasStartedSpeaking)
                {
                    Debug.Log($"检测到用户开始说话，音量: {currentVolume:0.000}, 阈值: {adjustedThreshold:0.000}");
                    hasStartedSpeaking = true;
                    speechStartSample = Microphone.GetPosition(null); // 记录语音开始的采样点
                }
                
                lastSoundTime = Time.time;
                speechEndSample = Microphone.GetPosition(null); // 持续更新语音结束点
                
                // 可视化反馈音量
                UpdateVoiceIndicatorLevel(currentVolume);
            }
            else if (hasStartedSpeaking && (Time.time - lastSoundTime) > silenceThresholdForSend)
            {
                Debug.Log($"检测到{silenceThresholdForSend}秒静音，结束当前段");
                break;
            }
            
            // 添加UI反馈
            if (voiceButtonText != null)
            {
                if (hasStartedSpeaking)
                {
                    float silenceDuration = Time.time - lastSoundTime;
                    if (silenceDuration > 0.5f)
                    {
                        voiceButtonText.text = $"静音检测中... {silenceThresholdForSend - silenceDuration:0.1f}s";
                    }
                    else
                    {
                        voiceButtonText.text = "录音中...";
                    }
                }
                else
                {
                    voiceButtonText.text = "等待说话...";
                }
            }
            
            yield return null;
        }
        
        // 停止录音
        Microphone.End(null);
        
        // 检查是否有有效语音内容
        if (hasStartedSpeaking && peakVolume > adjustedThreshold * 1.8f)
        {
            Debug.Log($"段录音完成，峰值音量: {peakVolume:0.000}, 时长: {recordingTime:0.0}秒");
            
            // 裁剪音频只保留语音部分
            if (speechStartSample < speechEndSample)
            {
                int startSample = (int)speechStartSample;
                int endSample = (int)speechEndSample;
                
                // 确保至少有500ms的语音
                int minSamples = 44100 / 2; // 半秒的采样数
                
                if (endSample - startSample >= minSamples)
                {
                    // 添加前后缓冲区 (200ms)
                    int bufferSamples = 44100 / 5;
                    startSample = Mathf.Max(0, startSample - bufferSamples);
                    endSample = Mathf.Min(currentSegment.samples, endSample + bufferSamples);
                    
                    Debug.Log($"裁剪音频：从 {startSample} 到 {endSample} 样本 (总 {currentSegment.samples})");
                    
                    // 创建新的裁剪后的AudioClip
                    int clipLength = endSample - startSample;
                    AudioClip trimmedClip = AudioClip.Create(
                        "TrimmedVoice", 
                        clipLength, 
                        currentSegment.channels, 
                        currentSegment.frequency, 
                        false
                    );
                    
                    // 复制数据
                    float[] samples = new float[clipLength];
                    currentSegment.GetData(samples, startSample);
                    trimmedClip.SetData(samples, 0);
                    
                    Debug.Log($"已裁剪语音片段，从 {recordingTime:0.0}秒 减少到 {clipLength / 44100f:0.0}秒");
                    
                    result.hasValidSpeech = true;
                    result.segment = trimmedClip;
                    
                    // 使用yield break代替return
                    yield break;
                }
            }
            
            // 如果无法裁剪，则使用原始片段
            result.hasValidSpeech = true;
            result.segment = currentSegment;
        }
        else
        {
            Debug.Log("未检测到有效语音，丢弃该段");
        }
    }

    // 新增: 从特定AudioClip获取音量级别
    float GetCurrentAudioLevelFrom(AudioClip clip)
    {
        if (clip == null || !Microphone.IsRecording(null))
            return 0;
        
        float[] samples = new float[256];
        int position = Microphone.GetPosition(null);
        
        // 确保有足够的数据可读
        if (position < samples.Length)
            return 0;
        
        // 从当前位置向前读取样本
        clip.GetData(samples, position - samples.Length);
        
        // 计算RMS音量
        float sum = 0;
        for (int i = 0; i < samples.Length; i++)
        {
            sum += samples[i] * samples[i];
        }
        
        // 应用非线性映射使小音量更敏感
        float rms = Mathf.Sqrt(sum / samples.Length);
        float nonLinearVolume = Mathf.Pow(rms, 0.8f); // 小音量时更敏感
        
        return nonLinearVolume;
    }

    // 新增：校准环境噪音
    IEnumerator CalibrateNoise(CalibrationResult result)
    {
        Debug.Log("开始校准环境噪音...");
        
        // 开始短暂录音以测量噪音
        AudioClip calibrationClip = Microphone.Start(null, false, 2, 44100);
        float calibrationTime = 1.0f;
        float calibrationTimer = 0;
        float calibrationSum = 0;
        int calibrationSamples = 0;
        
        while (calibrationTimer < calibrationTime)
        {
            calibrationTimer += Time.deltaTime;
            
            // 读取当前音量
            float[] samples = new float[256];
            int position = Microphone.GetPosition(null);
            
            if (position >= samples.Length && calibrationClip != null)
            {
                calibrationClip.GetData(samples, position - samples.Length);
                
                // 计算音量
                float sum = 0;
                for (int i = 0; i < samples.Length; i++)
                {
                    sum += samples[i] * samples[i];
                }
                float volume = Mathf.Sqrt(sum / samples.Length);
                
                calibrationSum += volume;
                calibrationSamples++;
            }
            
            yield return null;
        }
        
        // 停止校准录音
        Microphone.End(null);
        
        // 计算噪音阈值
        if (calibrationSamples > 0)
        {
            float avgBackgroundNoise = calibrationSum / calibrationSamples;
            result.threshold = Mathf.Max(0.02f, avgBackgroundNoise * 1.8f);
            Debug.Log($"环境噪音校准完成: {avgBackgroundNoise}, 设置阈值: {result.threshold}");
        }
        else
        {
            result.threshold = 0.02f;
            Debug.Log("环境噪音校准失败，使用默认阈值: 0.02");
        }
    }

    // 添加校准结果类
    public class CalibrationResult
    {
        public float threshold = 0.02f;
    }

    void Update()
    {
        // 检测回车键是否被按下
        if (Input.GetKeyDown(KeyCode.Return))
        {
            // 调用 OnSendButtonClick 函数来发送消息
            OnSendButtonClick();

            // 可选：取消激活输入框，使其失去焦点
            chatInput.DeactivateInputField();
        }
        
        // 如果启用了语音识别，检测特殊快捷键
        if (isVoiceRecognitionActive)
        {
            // 添加Escape键作为取消录音的快捷键
            if (Input.GetKeyDown(KeyCode.Escape))
            {
                Debug.Log("取消语音识别");
                isVoiceRecognitionActive = false;
                isRecording = false;
                Microphone.End(null);
                recordedClip = null; // 不处理录音
                UpdateVoiceButtonUI();
            }
        }
    }
}