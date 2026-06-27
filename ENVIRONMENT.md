# 环境说明

本项目环境分为四层：基础依赖、视频学习依赖、OCR 依赖和系统命令依赖。默认知识库调用只需要基础环境；视频学习和 OCR 是按需启用的能力包。

## 当前验证环境（macOS）

- Python：`3.12.13`
- 项目虚拟环境：`.venv/`
- `ffmpeg`：`/opt/homebrew/bin/ffmpeg`
- `ffprobe`：`/opt/homebrew/bin/ffprobe`
- `tesseract`：`/opt/homebrew/bin/tesseract`

不要为了补环境删除或重建现有 `.venv/`。当前环境已经能跑知识库工具、视频学习环境检查和 OCR 检查。

## Windows 迁移环境

后续迁移到 Windows 家用电脑时，推荐先按下面顺序补齐环境。Windows 不要求路径和 macOS 一致，只要求命令能在 PowerShell 中被找到。

### Windows 基础环境

- Python：建议安装 `Python 3.12.x`，并勾选 `Add python.exe to PATH`。
- Git：用于同步仓库。
- PowerShell：使用系统自带 PowerShell 即可。

创建虚拟环境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

安装基础 Python 依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

安装视频学习依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-video-learning.txt
```

安装 OCR 依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
```

### Windows 系统命令依赖

视频学习需要：

- `ffmpeg.exe`
- `ffprobe.exe`

OCR 需要：

- `tesseract.exe`
- Tesseract 中文简体语言包 `chi_sim`
- Tesseract 英文语言包 `eng`

推荐安装方式：

```powershell
winget install Gyan.FFmpeg
winget install UB-Mannheim.TesseractOCR
```

如果 `winget` 不可用，也可以手动安装 FFmpeg 和 Tesseract，但要确认安装目录已经加入 Windows `PATH`。

### Windows 环境检查

检查命令是否能找到：

```powershell
where.exe ffmpeg
where.exe ffprobe
where.exe tesseract
```

检查版本和语言包：

```powershell
ffmpeg -version
ffprobe -version
tesseract --version
tesseract --list-langs
```

`tesseract --list-langs` 里必须能看到：

```text
chi_sim
eng
```

迁移后的知识库系统检查：

```powershell
.\.venv\Scripts\python.exe -m tools.kb.cli --root . validate-system
.\.venv\Scripts\python.exe -m tools.kb.cli --root . dashboard
```

视频学习专项检查：

```powershell
.\.venv\Scripts\python.exe tools\check_video_learning_env.py
```

如果 Windows 上 `faster-whisper` 或底层推理库安装失败，优先补 Microsoft Visual C++ Redistributable 或 Visual Studio Build Tools，再重新安装 `requirements-video-learning.txt`。不要通过删除知识库目录解决依赖问题。

## 基础依赖

基础依赖安装：

```bash
.venv/bin/python -m pip install -r requirements.txt
```

`requirements.txt` 只放主环境最小依赖：

- `Pillow==12.2.0`

原因：主测试和图片元数据读取会直接使用 `PIL.Image`，所以基础环境需要 Pillow。项目其余核心工具主要使用 Python 标准库。

## 视频学习依赖

视频学习依赖安装：

```bash
.venv/bin/python -m pip install -r requirements-video-learning.txt
```

`requirements-video-learning.txt` 只放视频学习专用 Python 包：

- `faster-whisper`
- `scenedetect`

视频学习还依赖系统命令：

- `ffmpeg`
- `ffprobe`

视频学习专项检查：

```bash
.venv/bin/python tools/check_video_learning_env.py
```

期望结果：

- `ffmpeg` 有可执行路径。
- `ffprobe` 有可执行路径。
- `faster_whisper` 为 `true`。
- `scenedetect` 为 `true`。

## OCR 依赖

OCR 依赖安装：

```bash
.venv/bin/python -m pip install -r requirements-ocr.txt
```

`requirements-ocr.txt` 只放 OCR 专用 Python 包：

- `Pillow==12.2.0`
- `pytesseract==0.3.13`

`Pillow` 在 `requirements.txt` 和 `requirements-ocr.txt` 中重复声明是有意设计：OCR 能力包可以被单独安装使用，而单独安装 OCR 依赖时也必须具备图片读取能力。

OCR 还依赖系统命令：

- `tesseract`

OCR 当前使用 `chi_sim+eng` 语言组合。检查中文识别支持时，确认 `tesseract --list-langs` 输出里有 `chi_sim` 和 `eng`。

## 系统依赖检查

检查系统命令路径：

```bash
which ffmpeg
which ffprobe
which tesseract
```

检查系统命令版本：

```bash
ffmpeg -version
ffprobe -version
tesseract --version
tesseract --list-langs
```

如果系统命令缺失，先补系统依赖，再重跑专项检查。不要通过删除 `.venv/` 来解决系统命令缺失。

## 知识库系统检查

验证知识库索引、路由和系统状态：

```bash
.venv/bin/python -m tools.kb.cli --root . validate-system
.venv/bin/python -m tools.kb.cli --root . dashboard
```

## 已知提示

运行视频学习环境检查时，macOS 上可能出现 `av` 和 `cv2` 动态库重复加载提示。只要检查命令输出的 JSON 中对应项目为可用，不直接把该提示视为失败。

当前没有 `tools/check_env.py` 这个总环境检查脚本。如果后续需要一次性检查基础依赖、视频学习依赖、OCR 依赖和系统命令，再补一个总检查脚本。

## NAS 归档边界

`01_Case_Cleaning/video_learning/video_artifacts/` 已归档到 NAS，不属于本地必备环境。

NAS 路径：

```text
/Volumes/AFK/知识库学习文件/01_Case_Cleaning/video_learning/video_artifacts
```

后续如果需要回档学习、重跑转写、核查原视频或重新抽帧，先连接 NAS，再由本地代码按需移动或读取。
