import torch
import numpy as np
from PIL import Image
import io
import pyzipper
import os
import folder_paths
import datetime
import uuid
import cv2
import soundfile as sf
import tempfile

class HPSimpleZipSave:
    """
    HP-简单ZIP保存
    功能：将多模态数据(文本/图片/视频/音频)打包并直接保存为ZIP文件。
    """
    
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "filename_prefix": ("STRING", {"default": "HP_Zip"}),
            },
            "optional": {
                "password": ("STRING", {"default": "", "multiline": False, "tooltip": "解压密码"}),
                "text_content": ("STRING", {"multiline": True, "forceInput": True, "tooltip": "接入要隐藏的文字"}),
                "image_content": ("IMAGE", {"tooltip": "接入静态图片，将无损保存为PNG"}),
                "video_content": ("IMAGE", {"tooltip": "接入视频帧序列，将自动合成为MP4视频"}),
                "audio_content": ("AUDIO", {"tooltip": "接入音频数据，将保存为WAV"}),
                "fps": ("INT", {"default": 16, "min": 1, "max": 60, "step": 1, "tooltip": "仅对 video_content 生效"}),
                "video_quality": ("INT", {"default": 85, "min": 10, "max": 100, "step": 5, "tooltip": "仅对 video_content 生效，控制MP4视频体积"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("zip_path",)
    FUNCTION = "save_zip"
    CATEGORY = "HP-Media Multiplexer"
    OUTPUT_NODE = True  # 标记为输出节点，因为它会直接写盘

    def _build_zip_payload(self, password, text, images, video, audio, fps, video_quality):
        """构建ZIP数据包 (复用自 HPMediaFusionEncode)"""
        buffer = io.BytesIO()
        has_data = False
        
        task_uid = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        encryption_mode = pyzipper.WZ_AES if password else None
        
        with pyzipper.AESZipFile(buffer, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=encryption_mode) as zf:
            if password:
                zf.setpassword(password.encode('utf-8'))
            
            # 1. 文本
            if text and text.strip():
                zf.writestr(f"{task_uid}_text.txt", text.encode('utf-8'))
                has_data = True
                print(f"[HP-ZipSave] 已打包文本数据。")
                
            # 2. 音频
            if audio is not None:
                waveform = audio.get("waveform")
                sample_rate = audio.get("sample_rate", 44100)
                if waveform is not None:
                    audio_np = waveform.cpu().numpy()
                    if audio_np.ndim == 3: 
                        audio_np = audio_np.squeeze(0)
                    if audio_np.ndim == 2 and audio_np.shape[0] < audio_np.shape[1]:
                        audio_np = audio_np.T 
                        
                    abuf = io.BytesIO()
                    sf.write(abuf, audio_np, samplerate=sample_rate, format='WAV')
                    zf.writestr(f"{task_uid}_audio.wav", abuf.getvalue())
                    has_data = True
                    print(f"[HP-ZipSave] 已打包音频流。")

            # 3. 图片
            if images is not None:
                num_images = images.shape[0]
                for idx, img_tensor in enumerate(images):
                    img_np = (img_tensor.cpu().numpy() * 255.0).astype(np.uint8)
                    img_pil = Image.fromarray(np.clip(img_np, 0, 255).astype(np.uint8))
                    ibuf = io.BytesIO()
                    img_pil.save(ibuf, format='PNG')
                    
                    fname = f"{task_uid}_image_{idx:04d}.png"
                    zf.writestr(fname, ibuf.getvalue())
                has_data = True
                print(f"[HP-Append] 已打包 {num_images} 张无损 PNG 图片。")

            # 4. 视频
            if video is not None:
                num_frames = video.shape[0]
                print(f"[HP-Append] 正在后台合成 {num_frames} 帧视频 (FPS: {fps}, 质量: {video_quality})...")
                fd, temp_path = tempfile.mkstemp(suffix=".mp4")
                os.close(fd)
                try:
                    H, W = video.shape[1], video.shape[2]
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(temp_path, fourcc, fps, (W, H))
                    
                    out.set(cv2.VIDEOWRITER_PROP_QUALITY, video_quality)
                    
                    for img_tensor in video:
                        frame = (img_tensor.cpu().numpy() * 255.0).astype(np.uint8)
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        out.write(frame_bgr)
                    out.release()
                    
                    with open(temp_path, "rb") as f:
                        zf.writestr(f"{task_uid}_video.mp4", f.read())
                    has_data = True
                    print(f"[HP-ZipSave] 视频合成完毕: {task_uid}_video.mp4")
                finally:
                    if os.path.exists(temp_path): os.remove(temp_path)

        zip_payload = buffer.getvalue()
        buffer.close()
        
        if not has_data:
            print("[HP-ZipSave] ⚠️ 警告: 未检测到任何输入内容，未保存文件。")
            return b""
            
        return zip_payload

    def save_zip(self, filename_prefix, password="", text_content=None, image_content=None, video_content=None, audio_content=None, fps=16, video_quality=85, **kwargs):
        # 兼容旧参数 secret_image
        if 'secret_image' in kwargs and image_content is None:
            image_content = kwargs['secret_image']

        # 1. 构建ZIP数据
        zip_payload = self._build_zip_payload(password, text_content, image_content, video_content, audio_content, fps, video_quality)

        if not zip_payload:
            return {"ui": {"text": ["No content to save."]}, "result": ("",)}

        # 2. 保存 (使用 ComfyUI 标准路径)
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, 0, 0)
        
        file_name = f"{filename}_{counter:05}.zip"
        full_path = os.path.join(full_output_folder, file_name)

        with open(full_path, "wb") as f:
            f.write(zip_payload)

        print(f"[HP-ZipSave] ✅ ZIP文件已保存: {full_path}")
        
        # 返回 UI 更新
        return {"ui": {"text": [f"ZIP Saved: {file_name}"]}, "result": (full_path,)}
