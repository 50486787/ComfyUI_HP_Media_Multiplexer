import torch
import random

class HPImageSelector:
    """HP-图片随机选择器 (从批次中随机抽取一张)"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "输入图片批次 (Image Batch)"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "tooltip": "随机种子，控制选择哪一张"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("selected_image",)
    FUNCTION = "select"
    CATEGORY = "HP-Media Multiplexer"

    def select(self, images, seed):
        # images: Tensor (Batch, Height, Width, Channels)
        batch_size = images.shape[0]
        
        if batch_size == 0:
            # 防御性代码：如果输入为空，返回一个黑色占位图
            return (torch.zeros((1, 512, 512, 3)),)

        # 使用种子初始化随机数生成器，确保结果可复现
        rng = random.Random(seed)
        # 随机选择一个索引
        index = rng.randint(0, batch_size - 1)
        
        # 提取单张图片并保持维度 (1, H, W, C)
        selected_img = images[index].unsqueeze(0)
        
        print(f"[HP-Selector] 批次大小: {batch_size}, 种子: {seed} -> 选中索引: {index}")
        
        return (selected_img,)
