import torch
import numpy as np
from PIL import Image
import requests
import io

class HPWebImageLoader:
    """HP-网络图片加载器 (从API获取随机图)"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "https://picsum.photos/800/600?random=1", "multiline": False, "tooltip": "输入图片API地址"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "tooltip": "改变种子以强制重新下载图片"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "load_image"
    CATEGORY = "HP-Media Multiplexer"

    def load_image(self, api_url, seed):
        try:
            print(f"[HP-WebLoader] 正在请求 (Seed={seed}): {api_url}")
            # 增加 timeout 防止卡死
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            # 读取图片
            img = Image.open(io.BytesIO(response.content))
            
            # 统一转为 RGB 防止 RGBA/P 模式导致报错
            img = img.convert("RGB")
            
            # 转换为 ComfyUI 格式 (1, H, W, C) Float32
            img_np = np.array(img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np).unsqueeze(0)
            
            print(f"[HP-WebLoader] 获取成功: {img.width}x{img.height}")
            return (img_tensor,)
            
        except Exception as e:
            print(f"[HP-WebLoader] 获取失败: {e}")
            # 失败时返回黑色 512x512 图片，防止工作流崩溃
            return (torch.zeros((1, 512, 512, 3)),)
