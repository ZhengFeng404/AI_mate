using Live2D.Cubism.Framework.LookAt;
using UnityEngine;

public class ImprovedLookTarget : MonoBehaviour, ICubismLookTarget
{
    [SerializeField] private float sensitivityX = 3.0f; 
    [SerializeField] private float sensitivityY = 25.0f; // 增加Y轴灵敏度
    [SerializeField] private bool invertX = false;
    [SerializeField] private bool invertY = true; // 尝试反转Y轴方向
    [SerializeField] private bool trackOnlyWhileDragging = false;
    [SerializeField] private Vector3 offsetPosition = Vector3.zero;

    private Vector3 _lastPosition = Vector3.zero;

    public Vector3 GetPosition()
    {

        // 如果设置为只在拖动时跟踪，则检查鼠标按键
        if(trackOnlyWhileDragging && !Input.GetMouseButton(0))
        {
            return _lastPosition;
        }

        // 获取鼠标位置
        Vector3 mousePosition = Input.mousePosition;
        
        // 映射屏幕位置到-1到1范围
        float x = (mousePosition.x / Screen.width) * 2 - 1;
        float y = (mousePosition.y / Screen.height) * 2 - 1;
        
        // 应用反向设置
        if(invertX) x = -x;
        if(invertY) y = -y;
        
        // 应用灵敏度
        x *= sensitivityX;
        y *= sensitivityY;
        
        // 创建目标位置并应用偏移
        Vector3 targetPosition = new Vector3(x, y, 0) + offsetPosition;
        
        // 存储最后位置
        _lastPosition = targetPosition;
        
        // 输出调试信息
        // Debug.Log($"鼠标位置: {mousePosition}, 目标位置: {targetPosition}");
        
        return targetPosition;
    }


    public bool IsActive()
    {
        return true;
    }
}