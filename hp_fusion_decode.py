import torch
import numpy as np
import io
import struct
import pyzipper
import os
import tempfile
import cv2
from PIL import Image
import soundfile as sf
import folder_paths
import datetime
import uuid

class HPMediaFusionDecode:
    """HP-媒体特征解码器 (提取端 - 全模态分离输出 + 智能后缀寻址)"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "multiplexed_image": ("IMAGE", {"tooltip": "接入被融合过的图片"}),
                "verify_key": ("STRING", {"default": ""}),
                "fusion_depth": ("INT", {"default": 2, "min": 1, "max": 2, "step": 1}),
            }
        }

    # 5 个独立的输出端口！
    RETURN_TYPES = ("STRING", "IMAGE", "IMAGE", "AUDIO", "STRING")
    RETURN_NAMES = ("text_content", "image_content", "video_content", "audio_content", "zip_file_path")
    FUNCTION = "decode"
    CATEGORY = "HP-Media Multiplexer"

    def _create_dummy_image(self):
        """生成一张 1x1 的纯黑占位图片，防止 ComfyUI 因空输出而崩溃"""
        return torch.zeros((1, 1, 1, 3), dtype=torch.float32)

    def _create_dummy_audio(self):
        """生成一段极短的静音占位音频"""
        return {"waveform": torch.zeros((1, 1, 1), dtype=torch.float32), "sample_rate": 44100}

    def decode(self, multiplexed_image, verify_key, fusion_depth):
        # 默认只解密批次中的第一张图
        img_np = (multiplexed_image[0].cpu().numpy() * 255.0).astype(np.uint8)
        flat_img = img_np.flatten()

        # 1. 极速提取融合位
        extracted_vals = flat_img & ((1 << fusion_depth) - 1)
        
        # 2. 还原 Bit 数组
        if fusion_depth == 2:
            b1 = (extracted_vals >> 1) & 1
            b0 = extracted_vals & 1
            all_bits = np.column_stack((b1, b0)).flatten()
        else:
            all_bits = extracted_vals

        # 3. Bits 转 Bytes
        all_bytes = np.packbits(all_bits).tobytes()

        try:
            # 4. 解析头部 4 字节，获取真实载荷长度
            payload_len = struct.unpack('>I', all_bytes[:4])[0]
            
            # 防御性校验
            if payload_len == 0 or payload_len > len(all_bytes) - 4:
                print("[HP-Decode] 警告: 未检测到有效数据或长度异常。")
                return ("HP-Error: 未检测到有效数据。", self._create_dummy_image(), self._create_dummy_image(), self._create_dummy_audio(), "")

            # 5. 截取精确的 ZIP 密文流
            zip_bytes = all_bytes[4:4+payload_len]

            # 【特性5】：将整个加密的 ZIP 包物理写盘 (防止覆盖，增加随机UUID命名)
            task_uid = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            output_dir = folder_paths.get_output_directory()
            zip_save_path = os.path.join(output_dir, f"HP_Extracted_{task_uid}.zip")
            
            with open(zip_save_path, "wb") as f:
                f.write(zip_bytes)
            print(f"[HP-Decode] 成功提取物理加密包至: {zip_save_path}")

            # 初始化返回的容器 (带有安全占位符)
            out_text = ""
            out_images = []
            out_video = []
            out_audio = self._create_dummy_audio()

            # 6. 在内存中进行 AES 解密与智能分发
            buffer = io.BytesIO(zip_bytes)
            with pyzipper.AESZipFile(buffer, 'r') as zf:
                if verify_key:
                    zf.setpassword(verify_key.encode('utf-8'))
                file_list = zf.namelist()
                
                # 智能后缀寻址解析
                for file_name in file_list:
                    # [特性1]: 解析文字
                    if file_name.endswith('.txt'):
                        out_text = zf.read(file_name).decode('utf-8')
                        print(f"[HP-Decode] 成功解析文本: {file_name}")
                        
                    # [特性3]: 解析视频
                    elif file_name.endswith('.mp4'):
                        print(f"[HP-Decode] 正在后台解析视频序列: {file_name}")
                        fd, temp_mp4 = tempfile.mkstemp(suffix=".mp4")
                        os.close(fd)
                        try:
                            # 必须先落盘给 OpenCV 读
                            with open(temp_mp4, "wb") as f:
                                f.write(zf.read(file_name))
                            
                            cap = cv2.VideoCapture(temp_mp4)
                            while True:
                                ret, frame = cap.read()
                                if not ret: break
                                # BGR 转回 RGB
                                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                out_video.append(torch.from_numpy(frame_rgb).float() / 255.0)
                            cap.release()
                            print(f"[HP-Decode] 成功解析: {len(out_video)} 帧视频")
                        finally:
                            if os.path.exists(temp_mp4):
                                os.remove(temp_mp4)

                    # [特性4]: 解析音频
                    elif file_name.endswith('.wav'):
                        audio_data = zf.read(file_name)
                        # 使用 soundfile 极速读取内存音频流
                        data, samplerate = sf.read(io.BytesIO(audio_data))
                        
                        # soundfile 读出的是 (samples, channels)
                        if data.ndim == 1:
                            data = data.reshape(-1, 1) # 补齐通道维度
                        data = data.T # 翻转为 ComfyUI 要求的 (channels, samples)
                        
                        # 转为 Tensor 并加上 Batch 维度 (1, channels, samples)
                        audio_tensor = torch.from_numpy(data).float().unsqueeze(0)
                        out_audio = {"waveform": audio_tensor, "sample_rate": samplerate}
                        print(f"[HP-Decode] 成功解析音频: {file_name}")

                # [特性2]: 解析静态图片 (可能有多张)
                img_files = [f for f in file_list if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if img_files:
                    img_files.sort() # 保证图片序列顺序
                    for img_name in img_files:
                        img_data = zf.read(img_name)
                        pil_img = Image.open(io.BytesIO(img_data))
                        # 转回 ComfyUI Tensor 格式 (H, W, 3) 0.0-1.0
                        img_tensor = torch.from_numpy(np.array(pil_img).astype(np.float32) / 255.0)
                        out_images.append(img_tensor)
                    print(f"[HP-Decode] 成功解析 {len(out_images)} 张静态图片。")

            # 7. 整理最终输出张量 (如果没数据就丢占位符出去)
            final_images = torch.stack(out_images) if out_images else self._create_dummy_image()
            final_video = torch.stack(out_video) if out_video else self._create_dummy_image()
            
            # 如果文本完全为空，给个提示
            if not out_text and not out_images and not out_video and out_audio["waveform"].shape[-1] <= 1:
                out_text = "HP-Warning: 解压成功，但未找到支持的媒体格式。"

            return (out_text, final_images, final_video, out_audio, zip_save_path)
            
        except RuntimeError as e:
            if 'Bad password' in str(e) or 'password required' in str(e).lower():
                return ("HP-Error: 验证失败，verify_key 密码错误！", self._create_dummy_image(), self._create_dummy_image(), self._create_dummy_audio(), "")
            return (f"HP-Error: 解码异常 - {str(e)}", self._create_dummy_image(), self._create_dummy_image(), self._create_dummy_audio(), "")
        except Exception as e:
            return (f"HP-Error: 流解析失败。 - {str(e)}", self._create_dummy_image(), self._create_dummy_image(), self._create_dummy_audio(), "")