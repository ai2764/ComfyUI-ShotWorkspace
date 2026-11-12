# 剧本分镜与自动选素材

[English](SCRIPT_PLANNING.md) · [安装指南](INSTALL.zh-CN.md)

## 直接输入想拍的故事

在可选的 **Director Storyboard** 节点里写 **Story**：一句话、一段故事或零散想法都可以，不需要剧本格式、分镜编号或逐句对白。例如：“两个邻居在停电时第一次聊天。一个想借手电，另一个不愿承认自己也怕黑。轻松、有一点尴尬。”

可选导演指导，设置大致 **Target duration (seconds)**，点 **Plan shots**。一次模型请求直接提出全片分镜，需要时补对白，也可以是无对白镜头；不再强制先扩成剧本、接受草稿再分镜。审阅后点 **Use this plan (N shots)**，替换这个分镜节点的镜头列表。再点 **Apply storyboard to connected workspace** 才更新下游原节点；不接新节点时原节点照常手工使用。

Story 支持最多40,000字符。默认全片40秒，可设5–120秒；有大致的全片和英语对白时长预算，但不保证实际影片时长。用户明确提供的具名对白保留原文，否则模型可以创作；生成内容明确记录为模型从故事提出的方案，不冒充用户原文。素材已有描述用于约束外观与场景，不在此步重新读图或自动绑定图片。

已有详细剧本的用户可展开 **Have a finished script? (optional)**，粘贴到 **Existing script (optional)** 后用 **Plan existing script**，保留原严格对白／原文覆盖流程。正常用户无需打开这一项。

## 一次规划完整剧本

包内提供可选的[导演 profile 与台词指南](DIRECTOR_SKILLS.zh-CN.md)，说明目录导入、固定台词及单独授权的改写流程。

规划时先记录简短的事件表：谁向谁说话、提出什么请求、实际决定与行动是什么、结果如何。每镜关联事件，并记录起始状态、变化、结束状态及这个视角/切镜的作用。在草稿预览展开 **Story beat and framing purpose** 可检查。它们仍是模型提出的解释，并非独立核实过的故事事实。

添加分镜后，相关事件与镜头目的会随镜头保存，仅传给 description refinement。手动修改描述或台词后停用旧规划上下文，避免覆盖新意图；旧版分镜仍可使用。Refine 会检查人物意图、明确机位与视线，并留出动作和反应时间。这次不增加额外模型调用；耗时包括可能发生的校验修复。代码能检查关联与原文引用，不能保证语义理解或实际成片质量。

1. 在 **LLM connection** 配好 Writing model。规划分镜、选素材都用文本模型，不调用视觉模型。
2. 在 Director Storyboard 展开 **Have a finished script? (optional)**，粘贴完整剧本（包括原台词）。
3. 可选：导入 **SKILL.md** 或 **skill folder**。不导入时使用内置通用导演规则；目录包含 `profiles/*.md` 时选择一个 profile，不会把几种风格一起塞进去。
4. 点 **Plan existing script**，一次生成整份分镜，预览各镜描述、时长、台词及衔接意图。
5. 点 **Add all N shots**，将整批分镜追加到现有镜头后。手动镜头保留；新镜头继承规划时当前镜头的画幅尺寸，尚未选择参考图、也没有已接受的 H3 提示词，可以逐镜编辑。

规划不会生图、生成视频、改接线或自动写六段式 H3 prompt。衔接关系只是创作意图，实际上一镜媒体仍由外部接收工作流接入。指定的前镜 ID 会用于写作上下文，但不会自动读取上一镜视频。

每镜保留剧本原文片段用于追溯。校验拒绝遗漏原文覆盖、重复镜头键、非法时长、编造/重复台词和指向自身或未来镜头的衔接；对识别出的明确台词检查遗漏与顺序。剧情忠实度、含糊说话者仍需人工复核。单次最多 40,000 字符、48 镜；输入过大、模型截断或返回无效时，报错并保留现有镜头，不把半份结果当成完成。

## 为当前镜头自动选素材

导演指导用于故事分镜规划和描述优化。**Plan existing script**、**Refine description** 仍保留源剧本台词。每次记录实际生效的规则。读图、选素材、连接测试和 H3 prompt writer 不注入导演风格。

1. 在素材库添加图片，**Analyse image → Use description** 保存描述，或自行填写。人物身份、服装、道具等关键特征尽量描述清楚。
2. 选择已有镜头，写好镜头描述，点 Shot references 的 **Auto-select materials**。
3. Writing model 对比镜头标题、描述、台词与素材名称/已保存描述，选择有序的 0–9 张现有参考图，并列出缺失素材。
4. 结果只替换**当前镜头**的参考图选择，素材库文件和其他镜头不变。检查图片、必要时调整顺序，再 **Write prompt**。

选素材不发送像素；未保存描述的素材不会进入候选。不允许未知/重复素材 ID；找不到合适素材时可以一张不选并报告缺口。更改参考图会使已接受提示词过期。Refine、Write prompt 本身仍不在后台换素材。

请求期间如果改变剧本、skill、模型配置，或相关镜头/素材库输入，过时响应不会覆盖新内容。分镜草稿、导入知识和选择结果随 ComfyUI 工作流保存。

## 导演 skill 格式

单文件支持 UTF-8 Markdown；带引用文件时，用文件夹选择器选中直接包含 `SKILL.md` 的目录：

```text
director/
  SKILL.md
  references/shared.md
  profiles/baseline.md
  profiles/my-profile.md
```

入口示例：

```markdown
---
name: my-director
description: Shot planning guidance for my production.
---
# Directing method
Read [shared guidance](references/shared.md).
Plan cuts around changes in character action and audience information.
```

加载入口、递归引用的本地 `.md` 文件（Markdown 链接或行内代码路径）、选中 profile 及其引用。路径相对于引用它的文件；`..` 可以在包内解析，不能逃出包。`profiles/` 下未选中的文件不加载；远程 URL 不抓取。它是文本知识包加载器，不是会执行任意路由指令的通用 Agent，建议使用明确的本地引用。

最多 64 个 Markdown、总计 256 KiB，实际注入的选中知识最多 48,000 字符。缺引用文件会报错，应改用文件夹导入。不执行 Python/shell 等工具；外部 skill 不能覆盖节点固定输出契约，不支持导入自定义 JSON schema 或自动下载 skill 仓库。

每次规划请求都会先放入导演规则，再提供剧本。ComfyUI 用户目录的 `shot_workspace/llm_calls.jsonl`、`rule-bundles` 会记录版本、文件 SHA-256 与实际注入文本，用于确认发出了什么知识，不代表模型一定遵循或具名导演认可该 profile。导入的 Markdown 会嵌入保存的工作流，分享前检查内容及许可。
