# 安装与首次使用

[English](INSTALL.md) · [返回 README](../README.zh-CN.md) · [示例工作流](../examples/README.md)

## 先分清需要安装什么

| 组成 | 用途 | 如何准备 |
| --- | --- | --- |
| 可正常启动的 ComfyUI、Python 3.10+ | 加载节点和编辑界面 | 使用现有 ComfyUI 及其 Python 环境 |
| `aiohttp>=3.9`、`Pillow>=10` | 本节点的后端依赖 | 按下文安装本仓库 `requirements.txt` |
| OpenAI-compatible chat-completions 服务 | 读图、描述优化、写提示词 | 另行启动；读图模型必须支持图像输入 |
| 支持 H3 的 ComfyUI、兼容模型和接收工作流的社区节点 | 生成视频 | 按[示例说明](../examples/README.md)及对应上游说明安装 |

安装本包不会下载 LLM 或 H3 模型。不启动 LLM 也能打开编辑器；示例附有已接受的提示词，可先检查或测试视频通路，但修改镜头输入后提示词会失效，需要重写或复核接受。

## 1. 安装节点

按自己的版本选择**一种**方法，先关闭 ComfyUI，安装完成后正常启动。Git 命令需要先安装 [Git](https://git-scm.com/downloads)。目标文件夹已经存在时，按后面的更新步骤操作，不要重复克隆。

### Windows Portable 便携版

在 `ComfyUI_windows_portable` 文件夹打开 PowerShell；这个文件夹里面应同时有 `python_embeded` 和 `ComfyUI`：

```powershell
git clone https://github.com/ai2764/ComfyUI-ShotWorkspace.git .\ComfyUI\custom_nodes\ComfyUI-ShotWorkspace
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\ComfyUI-ShotWorkspace\requirements.txt
```

即使系统另装了 Python，也要用这里的 `python_embeded\python.exe`，否则依赖可能装错环境。完成后用平时的启动脚本启动 ComfyUI。

### 手动安装：Linux、macOS、Windows venv 或 Conda

激活**平时启动 ComfyUI 的同一个环境**，进入包含 `main.py` 和 `custom_nodes` 的 ComfyUI 根目录：

```sh
git clone https://github.com/ai2764/ComfyUI-ShotWorkspace.git custom_nodes/ComfyUI-ShotWorkspace
python -m pip install -r custom_nodes/ComfyUI-ShotWorkspace/requirements.txt
```

常见 `.venv` 激活命令：Linux/macOS 用 `source .venv/bin/activate`，Windows PowerShell 用 `.\.venv\Scripts\Activate.ps1`。Conda 用 `conda activate YOUR_COMFYUI_ENV`，把环境名换成自己的。不要为这个节点单独创建另一个环境。可核对当前 Python：

```sh
python -c "import sys; print(sys.executable)"
```

### ComfyUI Desktop

使用 Desktop 自带终端和该安装实际使用的 `custom_nodes` 目录，不要修改应用打包的程序文件，也不要直接用系统 Python。Desktop 的用户数据路径可能不同于手动安装版，应从自己的安装/启动信息确认目录。

将仓库克隆或解压到这个 `custom_nodes` 目录，在已激活 Desktop Python 环境的终端里执行：

```sh
python -m pip install -r "/actual/path/to/custom_nodes/ComfyUI-ShotWorkspace/requirements.txt"
```

将示例绝对路径换成自己的实际路径。若使用 Manager，可以在当前版本允许安装本仓库时通过它安装并重启；是否能搜索到节点、是否有 Git URL 安装入口，取决于 Manager 版本及安全设置。本指南不以 Manager 已收录为前提。各版本环境说明可参考 [ComfyUI 官方安装文档](https://docs.comfy.org/basic-concepts/custom-nodes)。

### 没有 Git：下载 ZIP

1. 仓库页面选择 **Code → Download ZIP**，解压。
2. 将包放进实际的 `ComfyUI/custom_nodes`，包文件夹命名为 `ComfyUI-ShotWorkspace`。
3. 检查下面的结构，不能变成 `ComfyUI-ShotWorkspace/ComfyUI-ShotWorkspace-main/__init__.py`，也不要保留两个启用的副本。
4. 跳过上面的 `git clone`，执行对应版本的依赖安装命令。

```text
ComfyUI/
  custom_nodes/
    ComfyUI-ShotWorkspace/
      __init__.py
      nodes.py
      requirements.txt
      web/
      examples/
```

### 确认安装成功

完整重启 ComfyUI 后端，再刷新网页；有缓存可用 Ctrl+F5 / Cmd+Shift+R。双击画布空白处，搜索 **Shot Workspace (prototype)**，分类为 **Shot Workspace**，打开后应看到 Shot workspace 编辑界面。**Workflow Interface**、**Shot Standard Media Outputs** 也由本包提供。

## 2. 首次连接 LLM

先单独启动模型服务。服务必须支持 OpenAI-compatible **`/chat/completions`**，读图还要支持真实图像输入，不限定模型品牌。

在 **LLM connection** 中填写：

| 字段 | 怎么填 |
| --- | --- |
| OpenAI-compatible URL | 例如服务端口设为 1234 时用 `http://127.0.0.1:1234/v1`；Ollama 默认兼容地址为 `http://127.0.0.1:11434/v1` |
| Writing model | 服务实际提供的模型 ID，不是随意起的显示名称 |
| Vision model | 支持图像输入的模型 ID；同一个模型支持两种能力时，两栏可填相同 ID |
| API key environment variable | 无认证的本地服务留空；需要密钥时填写环境变量名，例如 `SHOT_WORKSPACE_API_KEY` |

端口只是示例，以自己的模型服务为准。按供应商要求包含 `/v1`，不要再加 `/chat/completions`，节点会自动追加。请求由 **ComfyUI 后端**发出，因此 `127.0.0.1` 指后端所在机器/容器，不一定是浏览器所在电脑。文本和视觉角色目前共用一个 base URL。

如果服务需要认证，在**启动 ComfyUI 前**给启动环境设置密钥变量，编辑器里只填变量名。不要将密钥粘进变量名输入框或共享工作流。在无关终端设置变量，不会改变已经运行的 Desktop 进程。

点击 **Test connection**，它会真实请求文本 JSON 和一张蓝色测试图，两个角色都需要通过。这个测试不需要参考素材或生成工作流，成功只代表 LLM 通路可用，不代表视频生成已配置完成。

上下文容量由模型服务设置。**Unload LLM before generation** 默认关闭，首次配置建议保持关闭。开启时必须另配供应商支持、与 LLM 地址同源的卸载 URL；OpenAI-compatible 推理接口本身没有统一卸载协议。

## 3. 准备第一个镜头

1. 在素材库上传独立的人物、道具、场景图。
2. 点 **Analyse image**，核对结果，再点 **Use description** 保存；也可以手动填写描述。
3. 按 **Picture 1、Picture 2……** 的顺序选择当前镜头参考图，不需要手填参考图类型和 binding。
4. 输入粗略镜头想法，点 **Refine description**，再 **Write prompt** 并检查结果。读图、描述优化、写提示词分别显示耗时。
5. 点 **Workflow interface ↗** 定位或添加接口节点，按[接线说明](WORKFLOW_INTERFACE.md)把 prompt 和有序图像接到原工作流。模型、采样器、解码器、视频保存继续由原工作流负责。
6. 确认提示词已接受且对应当前输入，并有下游生成与保存分支，再点 **Generate this shot**。单独一个编辑器节点还不能生成视频。

保存 ComfyUI 工作流可保留镜头数据。参考图字节仍在 ComfyUI input 目录，仅分享 JSON 不会一并发送图片。

## 4. 跑通第一个示例

建议先用 [01 Motion Context 视频衔接](../examples/README.md#01--motion-context-with-video)。它是紧凑接入示例；另附的作者原布局参考图需要更多依赖。

1. 安装 [NikoDemon80 Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) 和 [H3-Optimizations](https://github.com/Zironic/H3-Optimizations)，按上游说明将各自依赖装进 ComfyUI Python 并重启，使用支持 H3 的 ComfyUI 版本。
2. 复制本仓库自带测试素材。**Windows Portable，在便携版根目录执行：**

   ```powershell
   .\python_embeded\python.exe .\ComfyUI\custom_nodes\ComfyUI-ShotWorkspace\tools\install_example_inputs.py --input-dir .\ComfyUI\input
   ```

   **手动/Desktop，在节点仓库目录、已激活 ComfyUI 环境的终端执行：**

   ```sh
   python tools/install_example_inputs.py --input-dir "/actual/path/to/ComfyUI/input"
   ```

   使用自己已存在的 input 目录。脚本复制五个测试文件，不覆盖同名但内容不同的文件，不下载模型或节点。
3. 将安装目录里的 `examples/verified/01-motion-context-video.json` 拖进 ComfyUI 画布，或用工作流 Open 命令打开。
4. 补齐缺失节点，在加载器选择本地已安装且兼容的 H3 diffusion、text encoder、video VAE 和 audio VAE。示例里的文件名不会自动下载；模型目录与显存配置按上游说明，以自己的硬件能承载为准。
5. 确认上一段视频加载器选中 `shot-workspace-example-previous.mp4`，必要时刷新选择器。首次不接 LLM 测试时，保持示例镜头输入不变，使用自带已接受提示词。
6. 执行队列并查看视频保存节点/结果。能打开编辑器或通过 Test connection，都不等于视频生成验证成功。

MultiRef 和原生 latent 衔接继续看[各示例说明](../examples/README.md)。原版 Motion Context 与 MultiRef 分支可能注册同名节点，必要时使用不同安装/配置。上一段结果需要明确选择，不会自动回接形成循环。

## 更新

Git 安装：进入 `custom_nodes/ComfyUI-ShotWorkspace`，执行：

```sh
git pull --ff-only
```

再按自己的版本重跑依赖安装命令，重启 ComfyUI、刷新浏览器。Git 提示冲突时先保留本地修改。ZIP 安装：备份自己的修改后替换为新版包，不保留两个启用副本。正常的 input 素材和已保存工作流位于包目录之外。

## 常见问题

| 现象 | 检查方法 |
| --- | --- |
| 找不到节点 / `IMPORT FAILED` | 查看后端启动 traceback；检查 `__init__.py` 层级、Python 3.10+、是否装进了当前实际启动的 ComfyUI；要重启后端，不只是刷新网页。 |
| 缺 `aiohttp` / `PIL` | 用 ComfyUI 的 Python 重装 requirements；`PIL` 来自 Pillow，便携版用 `python_embeded\python.exe`。 |
| 节点有了但界面空白/还是旧版 | 重启后强制刷新；仍失败时查看浏览器控制台和后端日志，检查是否存在重复包。 |
| LLM 拒绝连接、超时、404 | 检查模型服务、后端到服务的网络、端口与 API 前缀；base URL 不要以 `/chat/completions` 结尾；远端/容器后端的 localhost 不是自己电脑。 |
| 认证失败 / 找不到模型 | 核对服务实际的模型 ID，以及启动 ComfyUI 的进程是否继承了指定密钥变量。 |
| 文本通过，视觉失败 | Vision model 必须支持真实图像输入；文本模型不够，查看测试显示的供应商错误。 |
| 导入示例缺节点/模型 | 按该示例安装社区依赖并在加载器选择兼容权重，本包没有包含这些内容。 |
| Generate 提示没接输出 / 提示词过期 | 接好下游生成和保存分支；修改参考图、描述、镜头设置后，重写或复核接受提示词。 |
| 勾选卸载 LLM 后停止生成 | 先取消可选勾选，或配置并验证供应商支持、与 LLM 同源的卸载地址。 |
| 显存不足 | 按接收工作流说明选择硬件能承载的模型和设置；LLM 占同一 GPU 时，可在服务端卸载或配置可选卸载功能。本包没有通用最低显存承诺。 |
| 衔接没有使用上一镜 | 明确选中上一段 VIDEO 或兼容的原生 LATENT，保留原工作流 context/trim 接线；文件名和任意 latent 都不能直接当作 VIDEO。 |

仍无法解决时，请[提交 issue](https://github.com/ai2764/ComfyUI-ShotWorkspace/issues)，附操作系统、ComfyUI 安装方式/版本、节点 commit、失败步骤和相关 traceback。附日志或工作流前移除密钥、私有素材与个人配置。
