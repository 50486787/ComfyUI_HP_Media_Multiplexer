import hashlib
import zlib
from itertools import cycle

# ================= 核心字典 (256个单词) =================
# 必须与提供的 Python 脚本完全一致，以保证互通性
WORD_LIST = [
    # A - 30
    "about", "above", "act", "add", "after", "again", "age", "air", "all", "alone",
    "also", "always", "am", "an", "and", "animal", "another", "answer", "any", "appear",
    "apple", "area", "arm", "art", "as", "ask", "at", "atom", "away", "axis",
    # B - 54
    "baby", "back", "bad", "ball", "band", "bank", "bar", "base", "basic", "bat",
    "be", "bear", "beat", "beauty", "bed", "been", "before", "began", "begin", "behind",
    "best", "better", "between", "big", "bird", "bit", "black", "block", "blood", "blow",
    "blue", "board", "boat", "body", "bone", "book", "born", "both", "bottom", "box",
    "boy", "branch", "bread", "break", "bright", "bring", "brother", "brown", "build", "burn",
    "busy", "but", "buy", "by",
    # C - 64
    "cake", "call", "came", "camp", "can", "capital", "car", "card", "care", "carry",
    "case", "cat", "catch", "cause", "cell", "center", "century", "chair", "chance", "change",
    "check", "chick", "chief", "child", "choose", "circle", "city", "claim", "class", "clean",
    "clear", "climb", "clock", "close", "cloud", "coast", "coat", "cold", "color", "column",
    "come", "common", "cook", "cool", "copy", "corn", "corner", "correct", "cost", "cotton",
    "could", "count", "country", "course", "cover", "cow", "create", "crop", "cross", "crowd",
    "cry", "cup", "current", "cut",
    # D - 40
    "dad", "dance", "danger", "dark", "day", "dead", "deal", "dear", "death", "decide",
    "deep", "degree", "depend", "design", "desk", "develop", "die", "diff", "direct", "discuss",
    "distant", "divide", "do", "doctor", "dog", "dollar", "don", "done", "door", "double",
    "down", "draw", "dream", "dress", "drink", "drive", "drop", "dry", "duck", "during",
    # E - 33
    "each", "ear", "early", "earth", "ease", "east", "eat", "edge", "effect", "egg",
    "eight", "either", "electric", "element", "else", "end", "enemy", "energy", "engine", "enough",
    "enter", "equal", "even", "event", "ever", "every", "exact", "example", "except", "excite",
    "exercise", "expect", "eye",
    # F - 35
    "face", "fact", "fair", "fall", "family", "famous", "far", "farm", "fast", "fat",
    "father", "favor", "fear", "feed", "feel", "feet", "fell", "felt", "few", "field",
    "fig", "fight", "figure", "fill", "film", "final", "find", "fine", "finger", "finish",
    "fire", "first", "fish", "fit", "five", "flat", "floor", "flow", "flower", "fly",
    "food", "foot", "for", "force", "forest", "form", "forward", "four", "free", "friend",
    "from", "front", "fruit", "full", "fun"
]

# 自动补全至 256 (安全保险)
if len(WORD_LIST) < 256:
    for i in range(len(WORD_LIST), 256): WORD_LIST.append(f"tag{i}")

class CamouflageCryptoZlib:
    def __init__(self, password):
        # 如果密码为空，使用默认盐值，防止报错
        pwd = password if password else "default_salt"
        self.key_hash = hashlib.sha256(pwd.encode("utf-8")).digest()

    def xor_process(self, data_bytes):
        return b''.join(
            (b ^ k).to_bytes(1, 'big') 
            for b, k in zip(data_bytes, cycle(self.key_hash))
        )

    def encrypt_to_words(self, text):
        if not text: return ""
        data = text.encode("utf-8")
        
        # Zlib 压缩
        compressed = zlib.compress(data, level=9)
        
        # XOR 加密
        xored = self.xor_process(compressed)
        
        # 映射为单词
        result_words = []
        for byte in xored:
            safe_index = byte % len(WORD_LIST)
            result_words.append(WORD_LIST[safe_index])
        
        return ", ".join(result_words)

    def decrypt_from_words(self, text_words):
        if not text_words: return ""
        clean_text = text_words.replace(",", " ")
        words = clean_text.strip().split()
        
        data_bytes = bytearray()
        word_map = {w: i for i, w in enumerate(WORD_LIST)}
        
        for w in words:
            w = w.lower().strip()
            if w in word_map:
                data_bytes.append(word_map[w])
        
        # XOR 解密
        decrypted_compressed = self.xor_process(data_bytes)
        
        # Zlib 解压
        try:
            original_bytes = zlib.decompress(decrypted_compressed)
            return original_bytes.decode("utf-8")
        except (zlib.error, Exception):
            # 密码错误或解压失败时，直接返回原文，不报错
            return text_words

class HPTextEncode:
    """HP-文本伪装编码 (将文本加密为单词列表)"""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "", "tooltip": "输入要加密的文本"}),
                "password": ("STRING", {"default": "", "multiline": False, "tooltip": "加密密码"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("encoded_text",)
    FUNCTION = "encode"
    CATEGORY = "HP-Media Multiplexer"

    def encode(self, text, password):
        crypto = CamouflageCryptoZlib(password)
        result = crypto.encrypt_to_words(text)
        print(f"[HP-TextEncode] 加密完成，长度: {len(text)} -> {len(result)}")
        return (result,)

class HPTextDecode:
    """HP-文本伪装解码 (将单词列表还原为文本)"""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "encoded_text": ("STRING", {"multiline": True, "default": "", "forceInput": True, "tooltip": "输入加密后的单词列表"}),
                "password": ("STRING", {"default": "", "multiline": False, "tooltip": "解密密码"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("decoded_text",)
    FUNCTION = "decode"
    CATEGORY = "HP-Media Multiplexer"

    def decode(self, encoded_text, password):
        crypto = CamouflageCryptoZlib(password)
        result = crypto.decrypt_from_words(encoded_text)
        print(f"[HP-TextDecode] 解密尝试完成。")
        return (result,)
