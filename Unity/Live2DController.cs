using UnityEngine;
using UnityEngine.UI;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework.Expression;
using Live2D.Cubism.Framework.Motion;
using Live2D.Cubism.Framework; // 通用框架命名空间
using System;
using System.Collections;
using TMPro;

namespace AI_Mate
{
    public class Live2DController : MonoBehaviour
    {
        [Header("参考组件")]
        public Live2DModelManager modelManager;
        public ChatManager chatManager;
        public AudioManager audioManager;
        public APIClient apiClient;
        public VoiceRecognitionManager voiceManager;
        public IDManager idManager;

        [Header("用户ID界面")]
        public GameObject idPanel;
        public TMP_InputField idInputField;
        public Button confirmIdButton;
        public TextMeshProUGUI currentIdDisplay;

        // UI组件
        public TMP_InputField chatInput;
        public Button sendButton;
        public TextMeshProUGUI chatContent;
        public ScrollRect chatScrollRect;

        // 语音识别相关组件
        [Header("语音识别")]
        public Button voiceRecognitionToggleButton;
        public TextMeshProUGUI voiceButtonText;
        public Image voiceButtonImage;
        public Sprite micOnSprite;
        public Sprite micOffSprite;
        public GameObject voiceIndicator;

        private void Start()
        {
            // 初始化组件，如果未分配则创建
            SetupComponents();

            // 初始化各模块
            InitializeModules();

            // 设置快捷键检测
            SetupKeyboardShortcuts();

            // 在开始时播放指定的表情
            // PlayInitialExpression();
        }



        private void SetupComponents()
        {
            // 检查并创建必要的组件
            if (modelManager == null)
            {
                modelManager = gameObject.AddComponent<Live2DModelManager>();
                // 设置Live2D模型引用
                modelManager.model = GetComponent<CubismModel>();
                modelManager.expressionController = GetComponent<CubismExpressionController>();
                modelManager.motionController = GetComponent<CubismMotionController>();
                modelManager.motionClips = GetComponentInParent<Live2DController>().GetComponentInChildren<Live2DModelManager>()?.motionClips;
            }

            if (chatManager == null)
            {
                chatManager = gameObject.AddComponent<ChatManager>();
                chatManager.chatInput = chatInput;
                chatManager.sendButton = sendButton;
                chatManager.chatContent = chatContent;
                chatManager.chatScrollRect = chatScrollRect;
            }

            if (audioManager == null)
            {
                audioManager = gameObject.AddComponent<AudioManager>();
            }

            if (apiClient == null)
            {
                apiClient = gameObject.AddComponent<APIClient>();
            }

            if (voiceManager == null)
            {
                voiceManager = gameObject.AddComponent<VoiceRecognitionManager>();
                voiceManager.voiceRecognitionToggleButton = voiceRecognitionToggleButton;
                voiceManager.voiceButtonText = voiceButtonText;
                voiceManager.voiceButtonImage = voiceButtonImage;
                voiceManager.micOnSprite = micOnSprite;
                voiceManager.micOffSprite = micOffSprite;
                voiceManager.voiceIndicator = voiceIndicator;
            }

            if (idManager == null)
            {
                idManager = gameObject.AddComponent<IDManager>();
                idManager.idPanel = idPanel;
                idManager.idInputField = idInputField;
                idManager.confirmIdButton = confirmIdButton;
                idManager.currentIdDisplay = currentIdDisplay;
            }
        }

        private void InitializeModules()
        {
            // 初始化模块之间的连接
            idManager.Initialize(OnUserIDChanged);

            apiClient.Initialize(OnAIMessageReceived, OnAPIError);

            chatManager.Initialize(OnUserSendMessage);

            voiceManager.Initialize(OnAudioRecorded, OnVoiceRecognitionStateChanged, () => audioManager.isTTSPlaying);
        }

        // 回调处理方法
        private void OnUserIDChanged(string newUserId)
        {
            Debug.Log($"用户ID已更新为: {newUserId}");
        }

        private void OnUserSendMessage(string message, string userId)
        {
            StartCoroutine(apiClient.SendChatRequest(message, idManager.GetCurrentUserID()));
        }

        private void OnAIMessageReceived(AIMessage message)
        {
            // 处理AI回复
            chatManager.AddAIMessage(message);

            // 处理表情和动作
            if (!string.IsNullOrEmpty(message.expression))
                modelManager.SetExpression(message.expression);

            if (!string.IsNullOrEmpty(message.motion))
                modelManager.PlayMotion(message.motion);

            // 处理音频
            if (!string.IsNullOrEmpty(message.audioUrl))
                audioManager.EnqueueAudio(message.audioUrl);
        }

        private void OnAPIError(string errorMessage)
        {
            chatManager.AddErrorMessage(errorMessage);
        }

        private void OnAudioRecorded(AudioClip recordedClip)
        {
            if (recordedClip != null)
            {
                StartCoroutine(apiClient.SendVoiceRecognitionRequest(recordedClip, idManager.GetCurrentUserID()));
            }
        }

        private void OnVoiceRecognitionStateChanged(bool isActive)
        {
            Debug.Log($"语音识别状态: {(isActive ? "激活" : "停用")}");
        }

        // 快捷键支持
        private void SetupKeyboardShortcuts()
        {
            // 这些功能将在Update中处理
        }

        private void Update()
        {
            // 检测回车键是否被按下
            if (Input.GetKeyDown(KeyCode.Return))
            {
                // 如果聊天输入框有焦点，则发送消息
                if (chatInput.isFocused && !string.IsNullOrWhiteSpace(chatInput.text))
                {
                    chatManager.OnSendButtonClick();
                    chatInput.DeactivateInputField();
                }
            }

            // 添加Escape键作为取消录音的快捷键
            //if (Input.GetKeyDown(KeyCode.P) && voiceManager != null)
            //{
            //    voiceManager.ToggleVoiceRecognition();
            //}
        }

        // 公共方法：显示用户ID面板
        public void ShowIdPanel()
        {
            idManager.ShowIdPanel();
        }
    }
}