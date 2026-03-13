# HF ComfyUI Downloader

一个基于 Python `tkinter` 的桌面小工具，用来把 Hugging Face 上的模型文件下载到 ComfyUI 指定目录。

它支持：

- 输入 `huggingface.co` 或 `hf-mirror.com` 的仓库页面地址
- 自动解析模型仓库、分支和文件列表
- 选择 ComfyUI 模型目录下的目标子目录
- 调用本地 `hf download` 下载单个文件
- 复用环境变量中的 `HF_TOKEN`，支持私有仓库
- 显示下载进度、已下载大小、速度和剩余时间
- 支持断点续传

## 截图对应能力

当前版本适合以下工作流：

1. 输入页面地址，例如：

```text
https://hf-mirror.com/tewea/z_image_turbo_bf16_nsfw/tree/main
```

2. 点击“读取文件”
3. 在文件列表中选择一个模型文件
4. 选择 ComfyUI 目标目录
5. 点击“下载选中文件”

## 项目结构

项目已经整理为根目录平铺结构，不再额外套一层同名包目录：

```text
hf-comfyui-downloader/
  app.py
  download_service.py
  hf_client.py
  hf_utils.py
  main.py
  pyproject.toml
  run.bat
  tests/
```

## 依赖要求

- Python 3.11+
- 已安装并可直接执行的 `hf` 命令
- 建议提前设置 `HF_TOKEN`

## 安装

```bash
python -m pip install -e .
```

如果你的网络环境包含 SOCKS 代理，本项目依赖里已经包含 `socksio`。

## 运行

```bash
python main.py
```

或者直接双击：

```text
run.bat
```

## 使用说明

### 1. 输入仓库地址

支持两类地址：

- `https://huggingface.co/<owner>/<repo>/tree/<revision>`
- `https://hf-mirror.com/<owner>/<repo>/tree/<revision>`

### 2. 读取文件列表

程序会调用 Hugging Face Hub API 获取仓库根目录下的文件，并在界面中列出文件大小。

### 3. 选择下载目录

默认 ComfyUI 根目录为：

```text
D:\ComfyUI\models
```

“常用目录”下拉框会自动读取这个目录下的一级子目录。

### 4. 下载与续传

下载是通过本地 `hf download` 完成的。

- 默认支持断点续传
- 不会主动传 `--force-download`
- 如果目标目录下已经存在未完成下载，程序会继续续传

### 5. 进度显示

界面进度不是读取 CLI 终端进度条，而是跟踪 Hugging Face 在本地写入的临时下载文件：

```text
.cache/huggingface/download/*.incomplete
```

因此可以更稳定地显示：

- 百分比
- 已下载大小 / 总大小
- 实时速度
- 剩余时间

## 网络说明

### 关于 `hf-mirror.com`

程序默认优先使用：

```text
https://hf-mirror.com
```

来解析仓库和构造页面地址。

### 关于大文件下载

部分大模型文件最终会跳转到 Hugging Face 的 Xet/CAS 存储链路，例如：

```text
cas-bridge.xethub.hf.co
```

这不是工具本身错误，而是 Hugging Face 大文件分发方式决定的。

因此：

- `hf-mirror.com` 负责页面与 Hub 接口
- 大文件真实下载链路可能仍落到 `xethub.hf.co`

如果你的本地网络对 `xethub` 直连很差，建议在 Clash 中让 `xethub.hf.co` 继续走代理。

## 测试

运行测试：

```bash
python -m unittest discover -s tests -v
```

## 常见问题

### 1. 读不到私有仓库

确认系统环境变量里已经设置：

```text
HF_TOKEN
```

### 2. 下载速度不稳定

优先排查：

- `hf-mirror.com` 是否可访问
- `cas-bridge.xethub.hf.co` 当前是否应走代理
- Clash 规则是否已经重载

### 3. 进度条不更新

请确认你运行的是最新版本程序；旧窗口不会自动热更新。

## 开发

常用命令：

```bash
python -m unittest discover -s tests -v
python -m py_compile main.py app.py download_service.py hf_client.py hf_utils.py
```
