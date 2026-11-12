# ComfyUI Shot Workspace

在 ComfyUI 节点里管理参考素材、完善镜头描述、编写 H3 视频提示词，通过 **Workflow Interface** 接到现有生成工作流。模型加载、采样、context 和解码继续由原工作流负责。

**0.2.0，实验性更新。** 菜单名称保留 **Shot Workspace (prototype)**，新增可选的 **Director Storyboard** 节点。

## 新增：导演分镜节点

从粗略故事一次生成完整分镜，再将审阅后的计划应用到 Shot Workspace。导演节点是可选扩展，原来的手动分镜流程可以继续使用。

1. 添加 **Director Storyboard (optional)**，将它的 `storyboard` 输出接到 Shot Workspace 的 `storyboard` 输入。
2. 在导演节点配置 OpenAI-compatible 写作模型，输入 **Story**，点击 **Plan shots**。模型决定镜头数量。
3. 审阅结果，点击 **Use this plan**，再点击 **Apply storyboard to connected workspace**。应用计划会替换已连接工作区的镜头列表，保留素材库；请先保存需要保留的工作流。
4. 在工作区上传并分析素材，自动选素材、优化镜头描述、写提示词，再接入原有视频生成工作流。

[下载导演 skill ZIP](downloads/director-style-v2.2.4.zip)，解压后通过 **Import skill folder** 选择含 `SKILL.md` 的 `director-style` 文件夹。包含五种自行编写的导演风格指导和通用基线，仅注入分镜与描述优化步骤。

[导演 skill 使用说明](docs/DIRECTOR_SKILLS.zh-CN.md) · [分镜流程](docs/SCRIPT_PLANNING.zh-CN.md) · [最简接线示例](examples/director-storyboard-addon.json)

## 安装

先准备能正常启动的 ComfyUI（Python 3.10+）和 Git。没有 Git 可以用仓库 **Code → Download ZIP**，按[完整安装指南](docs/INSTALL.zh-CN.md)解压。依赖必须装进 **ComfyUI 使用的 Python 环境**，本包依赖为 `aiohttp>=3.9`、`Pillow>=10`。

**Windows Portable 便携版：** 在包含 `python_embeded` 的 `ComfyUI_windows_portable` 文件夹打开 PowerShell：

```powershell
git clone https://github.com/ai2764/ComfyUI-ShotWorkspace.git .\ComfyUI\custom_nodes\ComfyUI-ShotWorkspace
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\ComfyUI-ShotWorkspace\requirements.txt
```

**手动安装 / venv / Conda：** 先激活启动 ComfyUI 的环境，在 ComfyUI 根目录执行：

```sh
git clone https://github.com/ai2764/ComfyUI-ShotWorkspace.git custom_nodes/ComfyUI-ShotWorkspace
python -m pip install -r custom_nodes/ComfyUI-ShotWorkspace/requirements.txt
```

完整重启 ComfyUI 并刷新网页，在画布空白处双击，搜索 **Shot Workspace (prototype)**，分类为 **Shot Workspace**。确保 `custom_nodes/ComfyUI-ShotWorkspace/__init__.py` 直接存在，不能多套一层文件夹。

**[完整中文安装、首次配置与排错](docs/INSTALL.zh-CN.md)** · **[English installation guide](docs/INSTALL.md)**。包含 Desktop、ZIP、更新方法和第一个示例的完整步骤，不依赖 Manager 已收录本节点。

这是独立节点包，不是整合包，不含模型权重。ComfyUI/PyTorch 使用现有安装；LLM 功能需要另外启动兼容服务，视频生成需要另装接收工作流的社区节点和 H3 模型。Test connection 成功只代表 LLM 接口通过测试。

## 使用

**可选扩展：[Director Storyboard 导演分镜节点](docs/SCRIPT_PLANNING.zh-CN.md)。** 原 Shot Workspace 仍可独立使用；需要时接入新节点，输入 rough idea／剧本、加载导演 skill 并规划全片，审阅后明确应用到原节点。每镜的 **Auto-select materials** 仍在原节点中使用。

1. LLM connection 填 OpenAI-compatible URL、文本模型和视觉模型，单独启动模型服务后点 Test connection。
2. 上传素材，Analyse image 读图，检查文字后 Use description 保存。
3. 为当前镜头选择有序参考图，填写描述，Refine description，再 Write prompt 并检查。
4. 点 **Workflow interface ↗** 定位或添加 Workflow Interface，将 prompt 和 image 输出接到下游入口，连接采样与保存后再 Generate this shot。

读图、描述优化、提示词编写分别计时。参考图类型和 binding 不要求用户手填。默认不卸载 LLM；开启时要配置同源、供应商支持的卸载地址。

## 示例

先看[示例安装与接线步骤](examples/README.md)。附带中性色块参考图、3 秒测试视频及静音音轨，可通过脚本复制到自己的 ComfyUI input 目录。

- **01 Motion Context 视频衔接**：紧凑采样模板，前段视频拆成图像、音频后接入。
- **02 MultiRef latent context**：保留 seitanism 原版 AV Extension 的 102 个原节点、20 个分组及布局，增加 6 个接入节点，启用一次 extension。
- **03 原生 H3 latent 衔接**：先生成并保存第一段 latent，再手动选择它继续生成。
- **[Pika H3 Flex＋Motion Context](examples/pika-motion-context/README.zh-CN.md)**：保留官方 22 个原节点的位置、尺寸与原始分组，提供空白首段／latent 续段模板；测试台词、提示词及人物素材已清空，使用前填写自己的内容。

前 01–03 项接线来源于已成功出视频的本地实例。公开副本替换了私有素材、提示词和配置，并用附带色块素材重新实际生成了四段视频，覆盖视频衔接、latent 首段与续接、MultiRef extension；小段输出样片与哈希一并附带，见[验证范围](examples/VERIFICATION.md)。新增 Pika 项是另行清空内容的创作模板：私有源样片已跑通，公开空白文件须先填写自己的素材和提示词再生成。

Motion Context 紧凑示例不是作者完整 v0.7 原图。作者原始 JSON 和保留原布局的接入参考另外提供；完整 v0.7 参考不宣称整套推理已通过。

## 衔接边界

一次队列只执行当前镜头。上一段视频或 latent 要明确选择；结果不会自动回接，也不支持同次执行的反馈环。不同 latent 格式不能仅凭端口同名互换；跨工作流优先复用原解码器，通过标准 VIDEO 转接。高级音视频端口目前只是显式透传。

不含私有素材、录屏工程、密钥或个人服务配置。自有代码采用 MIT，社区 JSON 与派生示例保留各自许可，见[第三方声明](THIRD_PARTY_NOTICES.md)。
