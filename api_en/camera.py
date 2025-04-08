import cv2
import base64
import logging

logger = logging.getLogger(__name__)

def initialize_camera():
    """初始化摄像头设备."""
    try:
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            logger.warning("无法打开摄像头")
            return None
        return camera
    except Exception as e:
        logger.error(f"摄像头初始化异常: {e}")
        return None

def capture_frame(camera):
    """从摄像头捕获一帧图像."""
    if camera is None:
        logger.warning("摄像头未初始化，无法捕获图像")
        return None
    try:
        ret, frame = camera.read()
        if not ret:
            logger.warning("摄像头读取失败")
            return None
        return frame
    except Exception as e:
        logger.error(f"摄像头帧捕获异常: {e}")
        return None

def encode_frame_to_base64(frame):
    """将图像帧编码为 Base64 字符串."""
    if frame is None:
        return None
    try:
        resized_frame = cv2.resize(frame, (480, 320))
        _, img_encoded = cv2.imencode('.jpg', resized_frame)
        image_bytes = img_encoded.tobytes()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        return base64_image
    except Exception as e:
        logger.error(f"图像编码为 Base64 异常: {e}")
        return None

def release_camera(camera):
    """释放摄像头资源."""
    if camera:
        try:
            camera.release()
        except Exception as e:
            logger.error(f"释放摄像头资源异常: {e}")

def capture_and_encode_image(camera):
    """
    整合摄像头操作流程：初始化、捕获、编码为 Base64，并释放资源.

    Returns:
        str: 图像的 Base64 编码字符串，如果失败则返回 None.
    """
    #camera = None # 初始化 camera 变量为 None，确保在 finally 块中可以安全释放
    try:
        #camera = initialize_camera()
        if not camera:
            return None # 初始化失败，直接返回 None

        frame = capture_frame(camera)
        if frame is None:
            return None # 帧捕获失败，返回 None

        base64_image = encode_frame_to_base64(frame)
        if not base64_image:
            return None # Base64 编码失败，返回 None

        return base64_image # 成功返回 Base64 字符串

    except Exception as e:
        logger.error(f"捕获和编码图像过程中发生异常: {e}")
        return None # 捕获或编码过程中发生任何异常，都返回 None
    #finally:
    #    release_camera(camera) # 确保在任何情况下都释放摄像头资源


if __name__ == '__main__':
    #  测试代码保持不变
    logging.basicConfig(level=logging.DEBUG)

    base64_image = capture_and_encode_image() #  使用新的整合函数进行测试
    if base64_image:
        print("成功捕获并编码图像为 Base64 (部分内容预览):")
        print(base64_image[:100] + "...")
    else:
        print("图像捕获和编码失败")