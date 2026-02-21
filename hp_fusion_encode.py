import torch
import torch.nn.functional as F
import numpy as np
import io
import struct
import pyzipper
import os
import math
import tempfile
import cv2
from PIL import Image
import soundfile as sf  # 彻底抛弃 torchaudio，解决依赖地狱
import datetime         # 用于生成时间戳
import uuid             # 用于生成唯一UUID

class HPMediaFusionEncode:
    """HP-媒体融合编码器 (写入端 - 独立多模态接口 + 随机混淆命名)"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "cover_image": ("IMAGE", {"tooltip": "接入封面图(多图自动取第一张)"}),
                "verify_key": ("STRING", {"default": ""}),
                "fusion_depth": ("INT", {"default": 2, "min": 1, "max": 2, "step": 1, "tooltip": "深度2容量大，深度1隐蔽高"}),
            },
            "optional": {
                "text_content": ("STRING", {"multiline": True, "forceInput": True, "tooltip": "接入要隐藏的文字"}),
                "image_content": ("IMAGE", {"tooltip": "接入静态图片，将无损保存为PNG"}),
                "video_content": ("IMAGE", {"tooltip": "接入视频帧序列，将自动合成为MP4视频"}),
                "audio_content": ("AUDIO", {"tooltip": "接入音频数据，将保存为WAV"}),
                
                "fps": ("INT", {"default": 16, "min": 1, "max": 60, "step": 1, "tooltip": "仅对 video_content 生效"}),
                "video_quality": ("INT", {"default": 85, "min": 10, "max": 100, "step": 5, "tooltip": "仅对 video_content 生效，控制MP4视频体积"}),
            }      
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("multiplexed_image",)
    FUNCTION = "encode"
    CATEGORY = "HP-Media Multiplexer"

    def _build_zip_payload(self, verify_key, text, images, video, audio, fps, video_quality):
        """将所有输入的数据打包进同一个 AES 加密 ZIP 中"""
        buffer = io.BytesIO()
        has_data = False
        
        # 核心：生成这批任务的全局唯一标识：格式如 20260220_153022_1a2b3c
        task_uid = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        # 逻辑修改：如果密码为空，则不使用加密
        encryption_mode = pyzipper.WZ_AES if verify_key else None
        
        with pyzipper.AESZipFile(buffer, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=encryption_mode) as zf:
            if verify_key:
                zf.setpassword(verify_key.encode('utf-8'))
            
            # 1. 塞入文字
            if text and text.strip():
                zf.writestr(f"{task_uid}_text.txt", text.encode('utf-8'))
                has_data = True
                print(f"[HP-Encode] 已打包文本数据。")
                
            # 2. 塞入音频 (原生 numpy + soundfile 极速写入)
            if audio is not None:
                waveform = audio.get("waveform")
                sample_rate = audio.get("sample_rate", 44100)
                if waveform is not None:
                    audio_np = waveform.cpu().numpy()
                    # 整理维度为 (Samples, Channels)
                    if audio_np.ndim == 3: 
                        audio_np = audio_np.squeeze(0)
                    if audio_np.ndim == 2 and audio_np.shape[0] < audio_np.shape[1]:
                        audio_np = audio_np.T 
                        
                    abuf = io.BytesIO()
                    sf.write(abuf, audio_np, samplerate=sample_rate, format='WAV')
                    zf.writestr(f"{task_uid}_audio.wav", abuf.getvalue())
                    has_data = True
                    print(f"[HP-Encode] 已打包音频流。")

            # 3. 塞入无损静态图片 (彻底摒弃压缩，使用纯正 PNG)
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
                print(f"[HP-Encode] 已打包 {num_images} 张无损 PNG 图片。")

            # 4. 塞入并合成视频 (接入视频压缩参数)
            if video is not None:
                num_frames = video.shape[0]
                print(f"[HP-Encode] 正在后台合成 {num_frames} 帧视频 (FPS: {fps}, 质量: {video_quality})...")
                fd, temp_path = tempfile.mkstemp(suffix=".mp4")
                os.close(fd)
                try:
                    H, W = video.shape[1], video.shape[2]
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(temp_path, fourcc, fps, (W, H))
                    
                    # 关键修改：通过 OpenCV 属性接口，强行压制视频质量 (0-100)
                    out.set(cv2.VIDEOWRITER_PROP_QUALITY, video_quality)
                    
                    for img_tensor in video:
                        frame = (img_tensor.cpu().numpy() * 255.0).astype(np.uint8)
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        out.write(frame_bgr)
                    out.release()
                    with open(temp_path, "rb") as f:
                        zf.writestr(f"{task_uid}_video.mp4", f.read())
                    has_data = True
                    print(f"[HP-Encode] 视频合成完毕: {task_uid}_video.mp4")
                finally:
                    if os.path.exists(temp_path): os.remove(temp_path)

        zip_payload = buffer.getvalue()
        buffer.close()
        
        if not has_data:
            raise ValueError("HP-Error: 未检测到任何输入内容！请连接文本、图片、视频或音频中的至少一项。")
            
        return zip_payload

    # 吸收所有的未知参数 (**kwargs) 防止因为旧节点连线报错
    def encode(self, cover_image, verify_key, fusion_depth, text_content=None, image_content=None, video_content=None, audio_content=None, fps=16, video_quality=85, **kwargs):
        
        # 兼容处理：如果由于前端缓存，传来了旧名字，我们悄悄转换
        if 'media_content' in kwargs and video_content is None:
            video_content = kwargs['media_content']
            
        # 调用打包器，获取最终的加密二进制流
        zip_payload = self._build_zip_payload(verify_key, text_content, image_content, video_content, audio_content, fps, video_quality)
        
        payload_len = len(zip_payload)
        full_payload = struct.pack('>I', payload_len) + zip_payload
        bits = np.unpackbits(np.frombuffer(full_payload, dtype=np.uint8))

        total_bits_needed = len(bits)
        bits_per_pixel = 3 * fusion_depth
        pixels_needed = math.ceil(total_bits_needed / bits_per_pixel)

        # ==========================================
        # 核心防弹机制：强制剥离第一帧，彻底杜绝重复压制
        # ==========================================
        img_tensor = cover_image[0]
        
        H, W, C = img_tensor.shape
        current_pixels = H * W
        
        # 【自适应画幅拉伸】
        if current_pixels < pixels_needed:
            scale_factor = math.sqrt(pixels_needed / current_pixels) * 1.01
            new_H = int(math.ceil(H * scale_factor))
            new_W = int(math.ceil(W * scale_factor))
            
            print(f"[HP-Multiplexer] 触发智能扩图！数据量({payload_len/1024:.2f}KB)，正将封面从 {W}x{H} 无损拉伸至 {new_W}x{new_H} ...")
            
            img_reshaped = img_tensor.unsqueeze(0).permute(0, 3, 1, 2)
            resized_tensor = F.interpolate(img_reshaped, size=(new_H, new_W), mode='bilinear', align_corners=False)
            img_tensor = resized_tensor.squeeze(0).permute(1, 2, 0)
        else:
            print(f"[HP-Multiplexer] 数据量({payload_len/1024:.2f}KB)，封面尺寸达标 ({W}x{H})，直接执行融合。")

        img_np = (img_tensor.cpu().numpy() * 255.0).astype(np.uint8)

        if fusion_depth == 2:
            if len(bits) % 2 != 0: bits = np.append(bits, [0])
            grouped_bits = (bits[0::2] << 1) | bits[1::2]
        else:
            grouped_bits = bits

        flat_img = img_np.flatten()
        mask = ~((1 << fusion_depth) - 1)
        req_len = len(grouped_bits)
        
        flat_img[:req_len] = (flat_img[:req_len] & mask) | grouped_bits
        
        encoded_np = flat_img.reshape(img_np.shape)
        encoded_tensor = torch.from_numpy(encoded_np.astype(np.float32) / 255.0)

        # 将生成的单张图片重新增加一个 Batch 维度返回：(H, W, C) -> (1, H, W, C)
        return (encoded_tensor.unsqueeze(0),)