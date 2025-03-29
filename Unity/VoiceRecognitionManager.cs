using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace AI_Mate
{
    public class VoiceRecognitionManager : MonoBehaviour
    {
        [Header("语音识别")]
        public Button voiceRecognitionToggleButton;
        public TextMeshProUGUI voiceButtonText;
        public Image voiceButtonImage;
        public Sprite micOnSprite;
        public Sprite micOffSprite;
        public GameObject voiceIndicator; // 可选：语音识别指示器

        // 语音控制参数
        private bool isVoiceRecognitionActive = false;
        private bool isRecording = false;
        private AudioClip recordedClip;
        private bool isProcessingAudioSegment = false;
        
        // 语音识别设置
        private bool continuousListeningMode = true;
        private float segmentMaxDuration = 15.0f;
        private float silenceThresholdForSend = 1.0f;
        
        // 回调
        private Action<AudioClip> onAudioRecorded;
        private Action<bool> onVoiceRecognitionStateChanged;

        // 获取外部音频播放状态的委托
        private Func<bool> isTTSPlayingGetter;

        public void Initialize(Action<AudioClip> audioRecordedCallback, 
                               Action<bool> stateChangedCallback,
                               Func<bool> ttSPlayingGetter)
        {
            onAudioRecorded = audioRecordedCallback;
            onVoiceRecognitionStateChanged = stateChangedCallback;
            isTTSPlayingGetter = ttSPlayingGetter;

            if (voiceRecognitionToggleButton != null)
            {
                voiceRecognitionToggleButton.onClick.AddListener(ToggleVoiceRecognition);
                UpdateVoiceButtonUI();
            }
        }

        // 切换语音识别状态
        public void ToggleVoiceRecognition()
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
            onVoiceRecognitionStateChanged?.Invoke(isVoiceRecognitionActive);
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
                onAudioRecorded?.Invoke(recordedClip);
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

        // 连续听模式
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

            // 校准环境噪音
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
                bool isTTSPlaying = isTTSPlayingGetter?.Invoke() ?? false;
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
                
                // 获取音频段
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
                    onAudioRecorded?.Invoke(result.segment);
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

        // 录制单个音频段
        IEnumerator RecordAudioSegment(float volumeThreshold, AudioSegmentResult result)
        {
            result.hasValidSpeech = false;
            result.segment = null;
            
            // 等待任何TTS播放完成
            bool isTTSPlaying = isTTSPlayingGetter?.Invoke() ?? false;
            while (isTTSPlaying)
            {
                yield return new WaitForSeconds(0.1f);
                isTTSPlaying = isTTSPlayingGetter?.Invoke() ?? false;
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
                bool currentTTSPlaying = isTTSPlayingGetter?.Invoke() ?? false;
                if (currentTTSPlaying)
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

        // 从特定AudioClip获取音量级别
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

        // 校准环境噪音
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
    }
} 