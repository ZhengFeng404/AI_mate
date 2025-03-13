using UnityEngine;
using UnityEngine.UI;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework.Expression;
using Live2D.Cubism.Framework.Motion;
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine.Networking;
using Newtonsoft.Json.Linq;
using TMPro; // 确保引入 TMPro 命名空间


[System.Serializable]
public class MotionClip
{
    public string name;
    public AnimationClip clip;
}

public class Live2DController : MonoBehaviour
{
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

    // 对话记录
    private List<string> chatHistory = new List<string>();
    
    // 控制参数
    private bool isWaitingResponse = false;
    private const float RequestCooldown = 1f;
    private const string ApiUrl = "http://127.0.0.1:5000/chat";

    void Start()
    {
        sendButton.onClick.AddListener(OnSendButtonClick);
        // 初始化对话记录
        chatHistory.Clear();
        UpdateChatUI();
    }

    // 添加对话记录
    void AddChatMessage(string userMessage, string responseMessage)
    {   
        // 添加时间戳然后更新 UI
        string timestamp = DateTime.Now.ToString("HH:mm:ss");
        chatHistory.Add($"[{timestamp}] <color=green>你：{userMessage}</color>");
        chatHistory.Add($"[{timestamp}] <color=black>AI：{responseMessage}</color>");
        UpdateChatUI();
    }

    // 更新 UI 显示
    void UpdateChatUI()
    {
        // 将对话记录拼接为字符串
        string chatText = string.Join("\n\n", chatHistory);
        
        // 更新 Text 组件
        chatContent.text = chatText;
        
        // 动态调整 Content 高度
        Canvas.ForceUpdateCanvases();
        chatContent.rectTransform.sizeDelta = new Vector2(
            chatContent.rectTransform.sizeDelta.x,
            chatContent.preferredHeight
        );

        // 自动滚动到底部
        chatScrollRect.verticalNormalizedPosition = 0f;
        Canvas.ForceUpdateCanvases();
    }

    void OnSendButtonClick()
    {
        if (!isWaitingResponse && !string.IsNullOrWhiteSpace(chatInput.text))
        {
            StartCoroutine(SendRequestCoroutine(chatInput.text.Trim()));
            chatInput.text = "";
        }
    }

    IEnumerator SendRequestCoroutine(string userText)
{
    isWaitingResponse = true;

    using (UnityWebRequest webRequest = new UnityWebRequest(ApiUrl, "POST"))
    {
        //  构建 JSON 对象 (C# 字典)
        JObject requestData = new JObject();
        requestData["user_input"] = userText; //  使用 "user_input" 作为 JSON 字段名称，与后端保持一致

        //  将 JSON 对象 转换为 JSON 字符串 (使用 Newtonsoft.Json 库)
        string jsonString = requestData.ToString(Newtonsoft.Json.Formatting.None); //  Formatting.None  表示不进行格式化，生成紧凑的 JSON 字符串

        //  将 JSON 字符串 编码为 UTF8 字节数组
        byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonString);

        webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
        webRequest.downloadHandler = new DownloadHandlerBuffer();
        webRequest.SetRequestHeader("Content-Type", "application/json");

        yield return webRequest.SendWebRequest();

            if (webRequest.result == UnityWebRequest.Result.Success)
            {
                    string responseString = webRequest.downloadHandler.text;
                    JObject json = JObject.Parse(responseString);

                    string expression = json["expression"].ToString();
                    string motion = json["motion"].ToString();
                    string audioPath = json["audio"].ToString();

                    string responseText = json["response_text"].ToString();
            
                    // 更新 AI 回复到对话记录
                    AddChatMessage(userText, responseText);

                    SetExpression(expression);
                    PlayMotion(motion);
                    PlayAudio(audioPath);    // ...处理成功响应...
            }
            else
            {
                Debug.LogError($"请求失败: {webRequest.error}");
            }
        }
        
        yield return new WaitForSeconds(RequestCooldown);
        isWaitingResponse = false;
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

    IEnumerator PlayAudioCoroutine(string path)
{
    Debug.Log($"<color=cyan>[Audio] 开始加载音频: {path}</color>");
    
    using (UnityWebRequest www = UnityWebRequestMultimedia.GetAudioClip(
        path, 
        path.EndsWith(".mp3") ? AudioType.MPEG : AudioType.WAV))
    {
        yield return www.SendWebRequest();
        
        Debug.Log($"<color=cyan>[Audio] 加载结果: {www.result}</color>");
        Debug.Log($"<color=cyan>[Audio] 错误信息: {www.error}</color>");
        Debug.Log($"<color=cyan>[Audio] 响应码: {www.responseCode}</color>");

        if (www.result == UnityWebRequest.Result.Success)
        {
            AudioClip clip = DownloadHandlerAudioClip.GetContent(www);
            
            Debug.Log($"<color=green>[Audio] 加载成功: {clip?.name ?? "null"} (长度: {clip?.length ?? 0}s)</color>");
            
            AudioSource audioSource = GetComponent<AudioSource>();
            if (audioSource == null)
            {
                Debug.LogError("AudioSource组件缺失！");
                yield break;
            }

            audioSource.clip = clip;
            Debug.Log("<color=yellow>[Audio] 开始播放...</color>");
            audioSource.Play();
            
            // 验证播放状态
            yield return new WaitForSeconds(0.1f);
            Debug.Log($"<color=yellow>[Audio] 播放状态: {audioSource.isPlaying}</color>");
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