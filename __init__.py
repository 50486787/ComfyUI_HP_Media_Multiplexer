from .hp_fusion_encode import HPMediaFusionEncode
from .hp_fusion_decode import HPMediaFusionDecode
from .hp_image_selector import HPImageSelector
from .hp_web_image_loader import HPWebImageLoader
from .hp_text_crypt import HPTextEncode, HPTextDecode
from .hp_simple_zip_append import HPSimpleZipSave
from .hp_simple_zip_decode import HPSimpleZipDecode

NODE_CLASS_MAPPINGS = {
    "HPMediaFusionEncode": HPMediaFusionEncode,
    "HPMediaFusionDecode": HPMediaFusionDecode,
    "HPImageSelector": HPImageSelector,
    "HPWebImageLoader": HPWebImageLoader,
    "HPTextEncode": HPTextEncode,
    "HPTextDecode": HPTextDecode,
    "HPSimpleZipSave": HPSimpleZipSave,
    "HPSimpleZipDecode": HPSimpleZipDecode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HPMediaFusionEncode": "HP-Pixel Fusion Encode (像素融合编码)",
    "HPMediaFusionDecode": "HP-Pixel Fusion Decode (像素融合解码)",
    "HPImageSelector": "HP-Image Selector (随机图片选择)",
    "HPWebImageLoader": "HP-Web Image Loader (网络图片加载)",
    "HPTextEncode": "HP-Text Scramble (文本混淆)",
    "HPTextDecode": "HP-Text Unscramble (文本还原)",
    "HPSimpleZipSave": "HP-Simple Zip Save",
    "HPSimpleZipDecode": "HP-Simple Zip Decode (Extract)"
}

WEB_DIRECTORY = "./js"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']