# 导演 profile 与台词

[English](DIRECTOR_SKILLS.md) · [剧本分镜](SCRIPT_PLANNING.zh-CN.md)

包内提供 [director-style skill](../authoring/skills/director-style/SKILL.md)，包含通用基线及 Anderson、Wilder、Coen、Fincher、Ozu 五种启发式 profile。它们是自行编写的技法解释，不是导演官方 skill，也不保证成片能被认出。重点是人物的说话策略、潜台词、由具体台词触发的倾听反应与关系变化，再结合构图和机位。

**实验性质：**模型输出尚未证明台词质量或导演辨识度稳定改善；部分结果编造事实，仍需要人工审查。

## 导入

在 **Director Storyboard (optional) → Import skill folder** 选择仓库中的 `authoring/skills/director-style` 文件夹，确保 `SKILL.md` 就在所选目录下，然后选择一个 profile。规划加载对应的精简包；描述优化加载共享规则与所选 profile，不混入其他导演或资料文章。

这是显式导入，不自动替换已有选择。导入内容保存为快照，更新后需要重新导入。

授权改写的长示例独立放在 `dialogue/` 中，仅在单独的改写任务读取，正常 planning/refine 不加载这些示例。

## 保留台词与授权改写

现有 **Plan all shots** 和 **Refine description** 仍保留剧本原台词。固定台词时，skill 主要调整说话方式、停顿、倾听、视线和镜头覆盖，不能靠描述里的几个风格词把台词变成另一套剧本。

用户明确允许改写时，先单独生成台词/剧本草稿，再规划分镜。可以先只给故事事实和人物目标，不给原句，完成后再并排比较原文，减少逐句换词。选定的改写稿成为新的源剧本，之后 planning/refine 就严格保留该稿。目前没有自动台词改写按钮。

对新的粗想法，使用 **Story → Plan shots → Use this plan → Apply storyboard to connected workspace**。完整剧本仍可通过可选的 **Plan existing script** 入口规划，保留原台词。

不靠新增身世、道具、精确时间或剧情动作制造辨识度；保留实际决定和结果，为说话与完整反应留出时长。台词、分镜与描述仍需人工审查，实际表演、时间与导演风格是否成立需要看视频。

## 维护

修改共享规则和 profile 后，在仓库根目录运行 `python tools/build_director_packets.py`；`--check` 可检查生成包是否过期。模型请求不会执行此脚本，导入也只读取 Markdown。

[来源说明](../authoring/skills/director-style/SOURCES.md) 区分参考访谈与自行编写的解释。测试报告应分别说明格式正确、故事忠实、台词质量、风格辨识度和实际视频效果，不能用其中一项替代其他结论。
