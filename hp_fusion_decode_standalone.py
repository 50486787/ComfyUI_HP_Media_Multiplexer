import os
import sys
import struct
import numpy as np
from PIL import Image
import time

# 依赖库: pip install numpy pillow
# 打包命令: pyinstaller --onefile hp_fusion_decode_standalone.py

def process_file(file_path):
    # 去除拖拽可能产生的引号
    file_path = file_path.strip('"').strip("'")
    
    print(f"\n[Processing] {os.path.basename(file_path)}")
    
    if not os.path.exists(file_path):
        print("❌ 错误: 文件不存在")
        return

    try:
        # 使用 PIL 读取图片 (替代 torch)
        img = Image.open(file_path).convert('RGB')
        img_np = np.array(img)
    except Exception as e:
        print(f"❌ 读取图片失败: {e}")
        return

    # 展平像素数组
    flat_img = img_np.flatten()
    
    found = False
    
    # === 尝试深度 2 (默认模式) ===
    # 逻辑: 每个像素存储 2 bit (b1, b0)
    vals = flat_img
    b1 = (vals >> 1) & 1
    b0 = vals & 1
    # 重新组合位流
    bits_d2 = np.column_stack((b1, b0)).flatten()
    # 转为字节
    bytes_d2 = np.packbits(bits_d2)
    
    # 检查头部 (前4字节为长度)
    if len(bytes_d2) >= 4:
        # 大端序解析长度
        len_d2 = struct.unpack('>I', bytes_d2[:4].tobytes())[0]
        # 校验长度是否合理
        if 0 < len_d2 <= len(bytes_d2) - 4:
            print(f"✅ 检测到隐藏数据 (深度: 2)")
            print(f"📦 数据大小: {len_d2 / 1024:.2f} KB")
            save_zip(file_path, bytes_d2[4:4+len_d2].tobytes())
            found = True

    # === 尝试深度 1 (高隐蔽模式) ===
    if not found:
        bits_d1 = vals & 1
        bytes_d1 = np.packbits(bits_d1)
        
        if len(bytes_d1) >= 4:
            len_d1 = struct.unpack('>I', bytes_d1[:4].tobytes())[0]
            if 0 < len_d1 <= len(bytes_d1) - 4:
                print(f"✅ 检测到隐藏数据 (深度: 1)")
                print(f"📦 数据大小: {len_d1 / 1024:.2f} KB")
                save_zip(file_path, bytes_d1[4:4+len_d1].tobytes())
                found = True
    
    if not found:
        print("⚠️ 未检测到有效的隐藏数据。")

def save_zip(original_path, data):
    # 保存到当前运行目录 (EXE所在目录)
    dir_name = os.getcwd() 
    base_name = os.path.basename(original_path)
    name_no_ext = os.path.splitext(base_name)[0]
    
    # 生成输出文件名
    out_name = f"{name_no_ext}_extracted.zip"
    out_path = os.path.join(dir_name, out_name)
    
    try:
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"💾 已保存至: {out_path}")
        print(f"💡 提示: 请使用解压软件打开该 ZIP 文件 (如有密码请输入)")
    except Exception as e:
        print(f"❌ 保存文件失败: {e}")

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("="*50)
    print("   HP-Pixel Fusion 独立解码器 (无Torch版)")
    print("   功能: 拖入图片 -> 自动提取 ZIP 到当前文件夹")
    print("="*50)
    
    # 支持直接拖拽文件到图标上启动
    if len(sys.argv) > 1:
        for f in sys.argv[1:]:
            process_file(f)
        input("\n按回车键退出...")
    else:
        # 交互式循环
        while True:
            try:
                path = input("\n👉 请将图片拖入此处 (或输入 q 退出): ").strip()
                if not path: continue
                if path.lower() in ["q", "quit", "exit"]: break
                
                process_file(path)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")
