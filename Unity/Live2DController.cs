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

        // 自动眨眼和呼吸功能设置
        [Header("模型动作设置")]
        public bool enableEyeBlink = true;  // 启用自动眨眼
        public bool enableBreathing = true; // 启用呼吸功能

        [Header("眨眼设置")]
        [Range(1.0f, 10.0f)]
        public float eyeBlinkTimeScale = 1.0f; // 眨眼时间比例
        [Range(1, 10)]
        public int blinkFrequency = 3; // 眨眼频率(次/分钟)

        [Header("呼吸设置")]
        [Range(0.1f, 10.0f)]
        public float breathDuration = 3.0f; // 呼吸周期时间(秒)
        [Range(0.0f, 1.0f)]
        public float breathAmplitude = 0.5f; // 呼吸幅度
        [Range(0.0f, 1.0f)] 
        public float normalizedOrigin = 0.5f; // 正规化原点
        public int breathChannel = 0; // 呼吸通道

        // 使用引用变量，而不是具体类型，以避免类型可能不存在的问题
        private GameObject _eyeBlinkController;  // 眨眼控制器
        private GameObject _breathController; // 呼吸控制器

        private void Start()
        {
            // 初始化组件，如果未分配则创建
            SetupComponents();

            // 初始化各模块
            InitializeModules();

            // 设置快捷键检测
            SetupKeyboardShortcuts();

            // 设置自动眨眼和呼吸功能
            SetupEyeBlinkAndBreath();
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

        /// <summary>
        /// 设置自动眨眼和呼吸功能
        /// </summary>
        private void SetupEyeBlinkAndBreath()
        {
            if (modelManager == null || modelManager.model == null)
            {
                Debug.LogError("[Live2DController] 无法设置自动眨眼和呼吸：模型组件为空");
                return;
            }

            var model = modelManager.model;

            // 设置自动眨眼功能
            if (enableEyeBlink)
            {
                try
                {
                    Debug.Log("[Live2DController] 正在设置自动眨眼功能...");

                    // 尝试查找所有可能的眨眼控制器类型
                    Type eyeBlinkControllerType = FindComponentType(new string[] {
                        "Live2D.Cubism.Framework.CubismEyeBlinkController",
                        "Live2D.Cubism.Framework.CubismAutoEyeBlinkController",
                        "Live2D.Cubism.Framework.MotionFade.CubismEyeBlinkController"
                    });

                    if (eyeBlinkControllerType == null)
                    {
                        Debug.LogError("[Live2DController] 无法找到眨眼控制器类型，请检查SDK版本");
                        return;
                    }

                    // 根据官方文档添加眨眼控制器
                    var eyeBlinkController = model.gameObject.GetComponent(eyeBlinkControllerType);
                    if (eyeBlinkController == null)
                    {
                        eyeBlinkController = model.gameObject.AddComponent(eyeBlinkControllerType);
                        Debug.Log($"[Live2DController] 已添加{eyeBlinkControllerType.Name}组件");
                    }

                    // 通过反射设置眨眼参数
                    var properties = eyeBlinkControllerType.GetProperties();
                    var blendModeProperty = eyeBlinkControllerType.GetProperty("BlendMode");
                    if (blendModeProperty != null)
                    {
                        var blendModeEnum = Type.GetType("Live2D.Cubism.Framework.CubismParameterBlendMode, Assembly-CSharp");
                        if (blendModeEnum != null)
                        {
                            var multiplyValue = Enum.Parse(blendModeEnum, "Multiply");
                            blendModeProperty.SetValue(eyeBlinkController, multiplyValue);
                            Debug.Log("[Live2DController] 设置眨眼混合模式为Multiply");
                        }
                    }

                    // 尝试设置时间比例
                    var timescaleProperty = eyeBlinkControllerType.GetProperty("Timescale");
                    if (timescaleProperty != null)
                    {
                        timescaleProperty.SetValue(eyeBlinkController, eyeBlinkTimeScale);
                        Debug.Log($"[Live2DController] 设置眨眼时间比例为 {eyeBlinkTimeScale}");
                    }
                    else
                    {
                        Debug.LogWarning("[Live2DController] 无法找到Timescale属性");
                    }

                    // 简化类型转换，确保正确获取GameObject引用
                    _eyeBlinkController = null;
                    if (eyeBlinkController is Component)
                    {
                        Component component = (Component)eyeBlinkController;
                        _eyeBlinkController = component.gameObject;
                        Debug.Log("[Live2DController] 从Component获取到GameObject引用");
                    }
                    else
                    {
                        Debug.LogError($"[Live2DController] 无法获取眨眼控制器的GameObject引用，类型: {(eyeBlinkController != null ? eyeBlinkController.GetType().Name : "null")}");
                    }

                    Debug.Log("[Live2DController] 眨眼功能设置完成");
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[Live2DController] 设置自动眨眼时出错: {ex.Message}\n{ex.StackTrace}");
                }
            }

            // 设置呼吸功能
            if (enableBreathing)
            {
                try
                {
                    Debug.Log("[Live2DController] 正在设置呼吸功能...");

                    // 尝试设置传统的呼吸参数
                    SetupTraditionalBreathing(model);
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[Live2DController] 设置呼吸功能时出错: {ex.Message}\n{ex.StackTrace}");
                }
            }
        }

        /// <summary>
        /// 查找可用的组件类型
        /// </summary>
        private Type FindComponentType(string[] possibleTypeNames)
        {
            foreach (var typeName in possibleTypeNames)
            {
                Type type = Type.GetType(typeName + ", Assembly-CSharp");
                if (type != null)
                {
                    Debug.Log($"[Live2DController] 找到类型: {type.FullName}");
                    return type;
                }
            }
            return null;
        }

        /// <summary>
        /// 直接用传统方式设置呼吸效果，不依赖具体的HarmonicMotion类
        /// </summary>
        private void SetupTraditionalBreathing(CubismModel model)
        {
            // 创建呼吸控制器组件
            var breathComponent = model.gameObject.AddComponent<BreathController>();
            breathComponent.Model = model;
            breathComponent.BreathDuration = breathDuration;
            breathComponent.BreathAmplitude = breathAmplitude;
            breathComponent.NormalizedOrigin = normalizedOrigin;

            _breathController = breathComponent.gameObject;
            Debug.Log("[Live2DController] 使用自定义BreathController设置呼吸功能");
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
            if (Input.GetKeyDown(KeyCode.Escape) && voiceManager != null)
            {
                voiceManager.ToggleVoiceRecognition();
            }
        }

        // 公共方法：显示用户ID面板
        public void ShowIdPanel()
        {
            idManager.ShowIdPanel();
        }

        // 启用或禁用自动眨眼
        public void SetEyeBlinkEnabled(bool enabled)
        {
            enableEyeBlink = enabled;
            
            if (_eyeBlinkController != null)
            {
                var components = _eyeBlinkController.GetComponents<MonoBehaviour>();
                foreach (var comp in components)
                {
                    if (comp.GetType().Name.Contains("EyeBlink"))
                    {
                        comp.enabled = enabled;
                        Debug.Log($"[Live2DController] 自动眨眼 {(enabled ? "启用" : "禁用")}");
                        break;
                    }
                }
            }
        }

        // 启用或禁用呼吸效果
        public void SetBreathingEnabled(bool enabled)
        {
            enableBreathing = enabled;
            
            if (_breathController != null)
            {
                var breathComp = _breathController.GetComponent<BreathController>();
                if (breathComp != null)
                {
                    breathComp.enabled = enabled;
                    Debug.Log($"[Live2DController] 呼吸效果 {(enabled ? "启用" : "禁用")}");
                }
            }
        }
    }

    /// <summary>
    /// 自定义呼吸控制器组件
    /// </summary>
    public class BreathController : MonoBehaviour
    {
        public CubismModel Model;
        public float BreathDuration = 3.0f;
        public float BreathAmplitude = 0.5f;
        public float NormalizedOrigin = 0.5f;

        private float _time = 0f;
        private CubismParameter[] _targetParameters;
        // 使用字典存储权重，而不是依赖Tag属性
        private System.Collections.Generic.Dictionary<string, float> _parameterWeights = new System.Collections.Generic.Dictionary<string, float>();

        private void Start()
        {
            if (Model != null)
            {
                // 查找要影响的参数
                var parameters = new System.Collections.Generic.List<CubismParameter>();
                AddParameterIfExists(parameters, "ParamAngleX", 0.2f);
                AddParameterIfExists(parameters, "ParamAngleY", 0.2f);
                AddParameterIfExists(parameters, "ParamAngleZ", 0.1f);
                AddParameterIfExists(parameters, "ParamBodyAngleX", 0.1f);
                AddParameterIfExists(parameters, "ParamBodyAngleY", 0.3f);
                AddParameterIfExists(parameters, "ParamBustY", 0.7f);

                _targetParameters = parameters.ToArray();
                Debug.Log($"[BreathController] 已找到 {_targetParameters.Length} 个参数用于呼吸效果");
            }
            else
            {
                Debug.LogError("[BreathController] Model is null!");
            }
        }

        private void AddParameterIfExists(System.Collections.Generic.List<CubismParameter> parameters, string paramId, float weight)
        {
            var param = Model.Parameters.FindById(paramId);
            if (param != null)
            {
                // 使用字典存储权重
                _parameterWeights[paramId] = weight;
                parameters.Add(param);
                Debug.Log($"[BreathController] 添加呼吸参数: {paramId}, 权重: {weight}");
            }
        }

        private void Update()
        {
            if (_targetParameters == null || _targetParameters.Length == 0)
                return;

            _time += Time.deltaTime;
            float value = Mathf.Sin(_time * (2 * Mathf.PI) / BreathDuration);

            foreach (var param in _targetParameters)
            {
                if (param == null) continue;

                // 从字典中获取权重
                float weight = 0.3f; // 默认权重
                if (_parameterWeights.TryGetValue(param.Id, out float storedWeight))
                {
                    weight = storedWeight;
                }

                // 计算呼吸效果值
                float range = param.MaximumValue - param.MinimumValue;
                float center = param.MinimumValue + range * NormalizedOrigin;
                float amount = range * BreathAmplitude * weight * value;

                // 应用值
                param.Value = center + amount;
            }
        }
    }
} 