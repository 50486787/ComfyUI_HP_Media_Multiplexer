import torch
import numpy as np
import io
import pyzipper
import os
import tempfile
import cv2
from PIL import Image
import soundfile as sf
import folder_paths
import shutil
import uuid

# [Hack] 强制向 ComfyUI 注册 .zip 为支持的图片格式
# 这样前端的 "Upload" 按钮才会允许选择 .zip 文件，且后端允许上传
if hasattr(folder_paths, "supported_image_extensions"):
    folder_paths.supported_image_extensions.add(".zip")

class HPSimpleZipDecode:
    """HP-简单ZIP解码 (提取端 - 支持ZIP文件或图片追加)"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "zip_file": ("STRING", {"default": "", "multiline": False, "tooltip": "上传的ZIP文件名 (点击下方按钮上传)"}),
            },
            "optional": {
                "file_path": ("STRING", {"default": "", "multiline": False, "tooltip": "可选：绝对路径覆盖 (优先级高于上传)"}),
                "password": ("STRING", {"default": "", "multiline": False, "tooltip": "解压密码"}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE", "IMAGE", "AUDIO", "STRING")
    RETURN_NAMES = ("text_content", "image_content", "video_content", "audio_content", "zip_file_path")
    FUNCTION = "decode"
    CATEGORY = "HP-Media Multiplexer"

    def _create_dummy_image(self):
        """生成占位图防止报错"""
        return torch.zeros((1, 1, 1, 3), dtype=torch.float32)

    def _create_dummy_audio(self):
        """生成占位音频防止报错"""
        return {"waveform": torch.zeros((1, 1, 1), dtype=torch.float32), "sample_rate": 44100}

    def decode(self, zip_file, file_path="", password=""):
        target_path = ""

        # 1. 优先检查 file_path (如果用户手动输入了路径)
        if file_path and file_path.strip():
            target_path = file_path.strip('"').strip("'")
        
        # 2. 如果没有 file_path，则使用 zip_file (上传/选择的文件)
        if not target_path or not os.path.exists(target_path):
            if zip_file:
                input_dir = folder_paths.get_input_directory()
                p = os.path.join(input_dir, zip_file)
                if os.path.exists(p):
                    target_path = p

        if not target_path or not os.path.exists(target_path):
            print(f"[HP-SimpleDecode] ❌ 文件不存在: {target_path}")
            return ("HP-Error: 文件不存在", self._create_dummy_image(), self._create_dummy_image(), self._create_dummy_audio(), "")

        # 初始化返回容器
        out_text = ""
        out_images = []
        out_video = []
        out_audio = self._create_dummy_audio()

        try:
            # 直接尝试用 pyzipper 打开文件 (支持 ZIP 或 追加图)
            with pyzipper.AESZipFile(target_path, 'r') as zf:
                if password:
                    zf.setpassword(password.encode('utf-8'))
                
                file_list = zf.namelist()
                print(f"[HP-SimpleDecode] 发现文件内容: {file_list}")

                # 1. 解析文本
                for file_name in file_list:
                    if file_name.endswith('.txt'):
                        try:
                            out_text = zf.read(file_name).decode('utf-8')
                            print(f"[HP-SimpleDecode] 解析文本: {file_name}")
                        except Exception as e:
                            print(f"[HP-SimpleDecode] 文本解析失败: {e}")
                    
                    # 2. 解析视频
                    elif file_name.endswith('.mp4'):
                        print(f"[HP-SimpleDecode] 解析视频: {file_name}")
                        fd, temp_mp4 = tempfile.mkstemp(suffix=".mp4")
                        os.close(fd)
                        try:
                            with open(temp_mp4, "wb") as f:
                                f.write(zf.read(file_name))
                            
                            cap = cv2.VideoCapture(temp_mp4)
                            while True:
                                ret, frame = cap.read()
                                if not ret: break
                                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                out_video.append(torch.from_numpy(frame_rgb).float() / 255.0)
                            cap.release()
                        finally:
                            if os.path.exists(temp_mp4): os.remove(temp_mp4)

                    # 3. 解析音频
                    elif file_name.endswith('.wav'):
                        try:
                            audio_data = zf.read(file_name)
                            data, samplerate = sf.read(io.BytesIO(audio_data))
                            if data.ndim == 1: data = data.reshape(-1, 1)
                            data = data.T
                            audio_tensor = torch.from_numpy(data).float().unsqueeze(0)
                            out_audio = {"waveform": audio_tensor, "sample_rate": samplerate}
                            print(f"[HP-SimpleDecode] 解析音频: {file_name}")
                        except Exception as e:
                            print(f"[HP-SimpleDecode] 音频解析失败: {e}")

                # 4. 解析图片 (排序后处理)
                img_files = [f for f in file_list if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if img_files:
                    img_files.sort()
                    for img_name in img_files:
                        try:
                            img_data = zf.read(img_name)
                            pil_img = Image.open(io.BytesIO(img_data))
                            img_tensor = torch.from_numpy(np.array(pil_img).astype(np.float32) / 255.0)
                            out_images.append(img_tensor)
                        except Exception as e:
                            print(f"[HP-SimpleDecode] 图片解析失败 {img_name}: {e}")

            # 整理输出
            final_images = torch.stack(out_images) if out_images else self._create_dummy_image()
            final_video = torch.stack(out_video) if out_video else self._create_dummy_image()

            # 保存 ZIP 文件副本到 output 目录
            output_dir = folder_paths.get_output_directory()
            task_uid = uuid.uuid4().hex[:8]
            zip_filename = f"HP_Extracted_{task_uid}.zip"
            zip_save_path = os.path.join(output_dir, zip_filename)
            
            shutil.copy2(target_path, zip_save_path)
            print(f"[HP-SimpleDecode] 已保存ZIP副本: {zip_save_path}")

            return (out_text, final_images, final_video, out_audio, zip_save_path)

        except RuntimeError as e:
            if 'Bad password' in str(e) or 'password required' in str(e).lower():
                return ("HP-Error: 密码错误！", self._create_dummy_image(), self._create_dummy_image(), self._create_dummy_audio(), target_path)
            return (f"HP-Error: {str(e)}", self._create_dummy_image(), self._create_dummy_image(), self._create_dummy_audio(), target_path)
        except pyzipper.zipfile.BadZipFile:
             return ("HP-Error: 未检测到有效ZIP数据", self._create_dummy_image(), self._create_dummy_image(), self._create_dummy_audio(), target_path)
        except Exception as e:
            print(f"[HP-SimpleDecode] 解码失败: {e}")
            return (f"HP-Error: {str(e)}", self._create_dummy_image(), self._create_dummy_image(), self._create_dummy_audio(), target_path)
