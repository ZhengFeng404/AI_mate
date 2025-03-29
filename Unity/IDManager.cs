using UnityEngine;
using TMPro;
using UnityEngine.UI;
using System;

namespace AI_Mate
{
    public class IDManager : MonoBehaviour
    {
        [Header("ID界面")]
        public GameObject idPanel; // ID输入面板
        public TMP_InputField idInputField;
        public Button confirmIdButton;
        public TextMeshProUGUI currentIdDisplay;
        
        private string currentUserID = "guest";
        private Action<string> onIDChanged;

        public void Initialize(Action<string> idChangedCallback)
        {
            onIDChanged = idChangedCallback;
            confirmIdButton.onClick.AddListener(OnConfirmID);

            // 确保所有ID相关UI均可见
            if (idPanel != null)
            {
                idPanel.SetActive(true);
            }

            // 加载保存的ID
            string savedId = PlayerPrefs.GetString("UserID");
            if(!string.IsNullOrEmpty(savedId))
            {
                idInputField.text = savedId;
                currentUserID = savedId;
                UpdateIdDisplay();
            }
            else
            {
                // 显示当前默认ID
                UpdateIdDisplay();
            }
        }
        
        public string GetCurrentUserID()
        {
            return currentUserID;
        }

        void OnConfirmID()
        {
            string newId = idInputField.text.Trim();
            if(string.IsNullOrEmpty(newId))
            {
                newId = "guest_" + UnityEngine.Random.Range(1000,9999);
                idInputField.text = newId;
            }

            currentUserID = newId;
            UpdateIdDisplay();
            // 移除隐藏面板的代码
            // idPanel.SetActive(false);

            // 保存到本地
            PlayerPrefs.SetString("UserID", newId);
            PlayerPrefs.Save();

            // 通知其他组件ID已变更
            onIDChanged?.Invoke(currentUserID);
        }

        // 更新ID显示
        private void UpdateIdDisplay()
        {
            if (currentIdDisplay != null)
            {
                currentIdDisplay.text = $"当前用户：{currentUserID}";
            }
        }

        // 修改ShowIdPanel方法，因为现在面板始终可见
        public void ShowIdPanel()
        {
            // 面板始终可见，所以这里只需要更新输入框内容
            idInputField.text = currentUserID;
            // 让输入框获得焦点
            idInputField.Select();
            idInputField.ActivateInputField();
        }
    }
} 