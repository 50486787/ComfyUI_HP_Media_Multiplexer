# HP-Media Multiplexer (HP-RH 媒体复用工具包)

**HP-Media Multiplexer** 是一个专为 ComfyUI 设计的媒体流处理与打包工具箱。

它的核心目标是解决云端跑图（如 RunningHub 等平台）时，生成结果分散（包含多张图片、视频、音频、文本等）导致下载和整理困难的问题。

通过本插件，你可以将一次工作流生成的所有多模态内容（Image, Video, Audio, Text）自动打包整合进一张“封面图”中。你只需要下载这一张图片，即可获得本次运行的所有结果，极大地简化了云端文件的存储与传输流程。

---

## 核心功能

### 1. 📦 多模态文件打包 (Simple Zip Save)
这是本插件最推荐的功能。它将生成的各类资源无损打包为 ZIP 文件并直接保存。

*   **功能特点**：
    *   **一键打包**：支持同时输入文本、图片批次、视频帧序列（自动合成 MP4）、音频（自动保存 WAV）。
    *   **无损存储**：内部采用 ZIP 存储，对原始画质/音质无任何损耗。
    *   **云端友好**：在云平台只需下载一个 ZIP 文件，即可带走整个工作流的产物。

### 2. 🧬 像素融合 (Pixel Fusion)
一种基于 LSB 的高级数据嵌入方式，将数据编码进图片的像素中。

*   **功能特点**：
    *   数据与画面深度融合，外观上几乎无法察觉差异。
    *   支持配套的解码节点，可直接在 ComfyUI 内部还原出原始的图片、视频和音频流，实现工作流之间的数据传递。

### 3. 🛠️ 实用工具集
为了配合打包工作流，提供了一系列辅助节点：
*   **HP-Image Selector**：从一批图片中随机挑选一张作为封面图。
*   **HP-Web Image Loader**：从网络 API（如 Picsum）自动获取随机图片作为封面，无需本地准备。
*   **HP-Text Scramble**：对提示词或文本进行混淆压缩，便于以更紧凑的格式传输。

---

## 节点说明

### 📥 打包与解包 (Zip 系列)

#### **HP-Simple Zip Save**
*   **输入**：
    *   `filename_prefix`: 文件名前缀。
    *   `text_content`: (可选) 需要打包的文本/Prompt。
    *   `image_content`: (可选) 需要打包的图片。
    *   `video_content`: (可选) 需要打包的视频帧（节点会自动合成为 MP4）。
    *   `audio_content`: (可选) 需要打包的音频。
    *   `password`: (可选) 设置 ZIP 包的访问密码。
*   **输出**：保存一个 ZIP 文件到 output 目录。

#### **HP-Simple Zip Decode (Extract)**
*   **输入**：
    *   `zip_file`: 上传或选择 ZIP 文件（点击节点下方的 "⬆️ Upload ZIP" 按钮即可上传）。
    *   `file_path`: (可选) 绝对路径覆盖，优先级高于上传的文件。
    *   `password`: (可选) 解压密码。
*   **输出**：
    *   自动解析并分离出 Text, Image, Video, Audio 连接到后续工作流。
    *   同时会在 output 目录自动生成一个提取出来的 `.zip` 文件副本。

---

### 🧬 融合与还原 (Fusion 系列)

#### **HP-Pixel Fusion Encode**
*   **功能**：将多模态数据（文本、图片、视频、音频）编码写入封面图的像素中（LSB隐写）。
*   **输入**：
    *   `cover_image`: 封面图（载体）。如果数据量过大，会自动拉伸图片尺寸以容纳数据。
    *   `verify_key`: (可选) 加密密码。
    *   `fusion_depth`: 融合深度 (1或2)。深度2容量更大，深度1隐蔽性更好。
    *   `text_content` / `image_content` / `video_content` / `audio_content`: 需要隐藏的各类媒体数据。
    *   `fps` / `video_quality`: 控制视频合成的参数。
*   **输出**：
    *   `multiplexed_image`: 融合了隐藏数据的图片。外观与原图几乎一致。

#### **HP-Pixel Fusion Decode**
*   **功能**：从融合图中读取并还原原始媒体数据。
*   **输入**：
    *   `multiplexed_image`: 包含隐藏数据的图片。
    *   `verify_key`: 解密密码。
    *   `fusion_depth`: 必须与编码时选择的深度一致。
*   **输出**：
    *   自动分离并还原 Text, Image, Video, Audio 到对应端口。
    *   `zip_file_path`: 同时会在 output 目录生成提取出的 ZIP 文件副本。
    
#### **HP-Fusion Standalone Decoder (独立提取器)**
*   位于插件目录下的 `hp_fusion_decode_standalone.exe`，专为无 ComfyUI 环境设计。
*   **操作逻辑**：
    1.  双击运行hp_fusion_decode_standalone.exe。
    2.  将由 `HP-Pixel Fusion Encode` 生成的图片**拖拽**进窗口。
    3.  程序会自动提取隐藏的 ZIP 包，并**保存到当前文件夹**。
---

### 🔧 辅助工具

#### **HP-Web Image Loader**
*   输入 API 地址（默认 Picsum），自动下载一张随机图。常用于没有合适封面图时，自动生成一张风景图作为“载体”。

#### **HP-Text Scramble / Unscramble**
*   将长文本转换为紧凑的单词列表格式，或反向还原。



---

## 安装方法

1.  进入 ComfyUI 的 `custom_nodes` 目录。
2.  将本插件文件夹放入即可。
3.  安装依赖库：
    ```bash
    pip install pyzipper soundfile opencv-python numpy pillow
    ```
4.  重启 ComfyUI。

---

## 常见问题

**Q: 如何查看打包的内容？**
A: 方法一：使用 `HP-Simple Zip Decode` 节点读取。
方法二（推荐）：直接解压生成的 `.zip` 文件。

**Q: 视频合成支持什么格式？**
A: 输入 `video_content` (Image Batch) 后，节点会自动调用 OpenCV 将其压制为 H.264 编码的 MP4 文件存入包内。你可以通过 `video_quality` 参数控制体积。
