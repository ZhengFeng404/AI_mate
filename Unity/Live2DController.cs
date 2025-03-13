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
            string url = audioQueue.Dequeue();
            yield return StartCoroutine(PlayAudioCoroutine(url));
            isPlayingAudio = false;
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
    }
}