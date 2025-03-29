using System;
using UnityEngine;

namespace AI_Mate
{
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

    // 用于语音识别的辅助类
    public class AudioSegmentResult
    {
        public bool hasValidSpeech;
        public AudioClip segment;
    }

    public class CalibrationResult
    {
        public float threshold = 0.02f;
    }
    
    // 用于API请求的类
    public class ChatRequest
    {
        public string user_input;
        public string user_id;
        public string image_base64;
    }
} 