using UnityEngine;

public class QuitApplicationOnEscape : MonoBehaviour
{
    void Update()
    {
        // 检测是否按下了 Escape 键
        if (Input.GetKeyDown(KeyCode.Escape))
        {
            // 退出应用程序
            Application.Quit();

#if UNITY_EDITOR
            // 在 Unity 编辑器中停止播放模式
            UnityEditor.EditorApplication.isPlaying = false;
#endif
        }
    }
}