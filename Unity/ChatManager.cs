using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace AI_Mate
{
    public class ChatManager : MonoBehaviour
    {
        // UI组件
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
            if (!string.IsNullOrWhiteSpace(chatInput.text))
            {
                string userText = chatInput.text.Trim();
                
                // 创建纯净用户消息
                UserMessage userMsg = new UserMessage{
                    timestamp = DateTime.Now.ToString("HH:mm:ss"),
                    userId = "你", // 可以从外部传入
                    content = userText
                };

                // 加入队列并立即显示
                messageQueue.Enqueue(userMsg);
                if (!isProcessingSegment)
                    StartCoroutine(ProcessMessageQueue());

                // 调用发送回调
                onSendMessage?.Invoke(userText, "你");
                
                // 清空输入框
                chatInput.text = "";
            }
        }

        // 处理消息队列
        System.Collections.IEnumerator ProcessMessageQueue()
        {
            isProcessingSegment = true;
            while (messageQueue.Count > 0)
            {
                object msg = messageQueue.Dequeue();

                if(msg is UserMessage userMsg)
                {
                    HandleUserMessage(userMsg);
                    // 清除之前的未完成AI消息
                    var incomplete = chatHistory.FindAll(e => e.isAI && !e.isComplete);
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

        // 处理用户消息
        void HandleUserMessage(UserMessage msg)
        {
            // 结束之前的AI回复（如果有未完成的）
            var incompleteAI = chatHistory.FindLast(e => e.isAI && !e.isComplete);
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

            UpdateChatUI();
        }

        // 处理AI消息
        void HandleAIMessage(AIMessage msg)
        {
            // 判断是否需要创建新条目
            bool isNewDialogueRound = !chatHistory.Exists(e => e.isAI && !e.isComplete);
            
            ChatEntry currentEntry = isNewDialogueRound ?
                null :
                chatHistory.FindLast(e => e.isAI && !e.isComplete);

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
            }
            else
            {
                // 追加到现有对话
                currentEntry.content += msg.content;
                currentEntry.isComplete = msg.isLast;
            }

            UpdateChatUI();
        }

        // 添加错误消息
        public void AddErrorMessage(string message)
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

        // 获取显示颜色
        string GetDisplayColor(string aiId)
        {
            int hash = aiId.GetHashCode();
            return ColorUtility.ToHtmlStringRGB(aiColors[Math.Abs(hash) % aiColors.Length]);
        }

        // 更新UI显示
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

        // 添加新的AI消息
        public void AddAIMessage(AIMessage msg)
        {
            messageQueue.Enqueue(msg);
            if (!isProcessingSegment)
                StartCoroutine(ProcessMessageQueue());
        }

        // 添加新的用户消息
        public void AddUserMessage(string userId, string content)
        {
            UserMessage userMsg = new UserMessage{
                timestamp = DateTime.Now.ToString("HH:mm:ss"),
                userId = userId,
                content = content
            };
            
            messageQueue.Enqueue(userMsg);
            if (!isProcessingSegment)
                StartCoroutine(ProcessMessageQueue());
        }
    }
} 