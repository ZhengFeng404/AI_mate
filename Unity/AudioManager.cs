using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;

namespace AI_Mate
{
    public class AudioManager : MonoBehaviour
    {
        private Queue<string> audioQueue = new Queue<string>();
        private bool isPlayingAudio = false;
        public bool isTTSPlaying = false;

        private AudioSource audioSource;

        private void Awake()
        {
            audioSource = GetComponent<AudioSource>();
            if (audioSource == null)
            {
                audioSource = gameObject.AddComponent<AudioSource>();
            }
        }

        private void Start()
        {
            StartCoroutine(AudioPlaybackCoordinator());
        }

        public void EnqueueAudio(string audioUrl)
        {
            if (!string.IsNullOrEmpty(audioUrl))
            {
                audioQueue.Enqueue(audioUrl);
            }
        }

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

        private IEnumerator PlayAudioCoroutine(string url)
        {
            using (UnityWebRequest www = UnityWebRequestMultimedia.GetAudioClip(url, AudioType.WAV))
            {
                yield return www.SendWebRequest();

                if (www.result == UnityWebRequest.Result.Success)
                {
                    AudioClip clip = DownloadHandlerAudioClip.GetContent(www);
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

        // 将AudioClip转换为WAV格式的字节数组
        public byte[] AudioClipToWav(AudioClip clip)
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
                    writer.Write(System.Text.Encoding.ASCII.GetBytes("RIFF"));
                    writer.Write(36 + intData.Length * 2);
                    writer.Write(System.Text.Encoding.ASCII.GetBytes("WAVE"));
                    writer.Write(System.Text.Encoding.ASCII.GetBytes("fmt "));
                    writer.Write(16);
                    writer.Write((short)1); // 音频格式，1表示PCM
                    writer.Write((short)clip.channels);
                    writer.Write(clip.frequency);
                    writer.Write(clip.frequency * clip.channels * 2); // 字节率
                    writer.Write((short)(clip.channels * 2)); // 块对齐
                    writer.Write((short)16); // 位深度
                    
                    // 数据块
                    writer.Write(System.Text.Encoding.ASCII.GetBytes("data"));
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
    }
} 