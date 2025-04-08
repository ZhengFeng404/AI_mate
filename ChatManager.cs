using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;
using System.Collections.Generic;

public class ChatManager : MonoBehaviour
{
    public TMP_InputField chatInput;
    public Button sendButton;
    public TextMeshProUGUI chatContent;
    public ScrollRect chatScrollRect;

    // 对话记录
    private List<ChatEntry> chatHistory = new List<ChatEntry>();
    private Queue<object> messageQueue = new Queue<object>();
    private bool isProcessingSegment = false;

    // 回调
    private Action<string, string> onSendMessage;

    private static readonly Color[] aiColors = new Color[]
    {
        new Color(0.2f, 0.4f, 0.7f), // 蓝色
        new Color(0.7f, 0.2f, 0.4f)  // 红色
    };

    // 初始化
    public void Initialize(Action<string, string> sendMessageCallback)
    {
        onSendMessage = sendMessageCallback;
        
        sendButton.onClick.AddListener(OnSendButtonClick);
        chatInput.onSubmit.AddListener((text) => OnSendButtonClick()); // 添加回车键提交监听
        chatInput.lineType = TMP_InputField.LineType.SingleLine; // 设置为单行模式
        chatHistory.Clear();
        UpdateChatUI();
    }

    private void Update()
    {
        // 检测Shift+Enter组合键
        if (Input.GetKey(KeyCode.Return) || Input.GetKey(KeyCode.KeypadEnter))
        {
            if (!Input.GetKey(KeyCode.LeftShift) && !Input.GetKey(KeyCode.RightShift))
            {
                OnSendButtonClick();
            }
        }
    }

    // 发送按钮点击
    public void OnSendButtonClick()
    {
        // ... existing code ...
    }
} 