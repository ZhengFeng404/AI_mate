// 在项目中新建 WavUtility.cs
using System.IO;
using UnityEngine;

public static class WavUtility
{
    public static AudioClip ToAudioClip(byte[] fileBytes)
    {
        using (var memoryStream = new MemoryStream(fileBytes))
        using (var binaryReader = new BinaryReader(memoryStream))
        {
            // WAV文件头解析
            var riffHeader = System.Text.Encoding.UTF8.GetString(binaryReader.ReadBytes(4));
            var chunkSize = binaryReader.ReadUInt32();
            var waveHeader = System.Text.Encoding.UTF8.GetString(binaryReader.ReadBytes(4));

            // 格式块解析
            var fmtHeader = System.Text.Encoding.UTF8.GetString(binaryReader.ReadBytes(4));
            var fmtChunkSize = binaryReader.ReadUInt32();
            var audioFormat = binaryReader.ReadUInt16();
            var numChannels = binaryReader.ReadUInt16();
            var sampleRate = binaryReader.ReadUInt32();
            var byteRate = binaryReader.ReadUInt32();
            var blockAlign = binaryReader.ReadUInt16();
            var bitsPerSample = binaryReader.ReadUInt16();

            // 数据块解析
            var dataHeader = System.Text.Encoding.UTF8.GetString(binaryReader.ReadBytes(4));
            var dataSize = binaryReader.ReadUInt32();
            var audioData = binaryReader.ReadBytes((int)dataSize);

            // 创建AudioClip
            var audioClip = AudioClip.Create(
                "Live2DAudio",
                (int)(dataSize / (bitsPerSample / 8)),
                (int)numChannels,
                (int)sampleRate,
                false
            );
            audioClip.SetData(ConvertByteToFloat(audioData, bitsPerSample), 0);
            return audioClip;
        }
    }

    private static float[] ConvertByteToFloat(byte[] source, int bitDepth)
    {
        var floatArray = new float[source.Length / (bitDepth / 8)];
        // 转换逻辑...
        return floatArray;
    }
}