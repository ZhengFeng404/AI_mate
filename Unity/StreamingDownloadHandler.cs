using System.Collections.Generic;
using System.Linq;
using UnityEngine.Networking;

namespace AI_Mate
{
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
} 