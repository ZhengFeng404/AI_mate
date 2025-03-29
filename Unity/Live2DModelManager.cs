using UnityEngine;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework.Expression;
using Live2D.Cubism.Framework.Motion;

namespace AI_Mate
{
    public class Live2DModelManager : MonoBehaviour
    {
        // Live2D组件
        public CubismModel model;
        public CubismExpressionController expressionController;
        public CubismMotionController motionController;
        public MotionClip[] motionClips;

        public void SetExpression(string expressionName)
        {
            if (expressionController == null || expressionController.ExpressionsList == null) return;

            for (int i = 0; i < expressionController.ExpressionsList.CubismExpressionObjects.Length; i++)
            {
                var expr = expressionController.ExpressionsList.CubismExpressionObjects[i];
                if (expr == null) continue;

                // 关键修改：去除后缀后匹配
                var exprName = expr.name.Replace(".exp3", "").Trim();
                if (exprName == expressionName)
                {
                    expressionController.CurrentExpressionIndex = i;
                    return;
                }
            }

            Debug.LogWarning($"Expression not found: {expressionName}");
        }

        public void PlayMotion(string motionName)
        {
            if (motionController == null) return;

            // 根据名称查找 AnimationClip
            AnimationClip clip = null;
            foreach (var motionClip in motionClips)
            {
                if (motionClip.name == motionName)
                {
                    clip = motionClip.clip;
                    break;
                }
            }

            if (clip != null)
            {
                // 调用内置方法，传入 AnimationClip 和优先级
                motionController.PlayAnimation(clip, priority: CubismMotionPriority.PriorityForce);
            }
            else
            {
                Debug.LogWarning("Animation clip not found: " + motionName);
            }
        }
    }
} 