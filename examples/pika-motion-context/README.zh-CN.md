# Pika H3 Flex＋Shot Workspace＋Motion Context

[English](README.md)

这两份是**空白创作模板**。测试故事、台词、提示词、人物素材及个人配置均已清空。保留 Pika 官方原有 22 个节点的位置、尺寸和原始分组；Workspace 与续接辅助节点放在原画布外侧。

## 依赖

需要支持 H3/Pika 的 ComfyUI、本节点包和 [H3 Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)，含兼容的 Load/Save Latent 与 Trim。原样片环境为 ComfyUI 0.38.0、FP16 视频 VAE、FP32 音频 VAE、强度 1 的 Pika H3 Flex 参考适配器、LCM 六步采样。模型加载器请选择本机兼容权重，不附带模型文件。

原有两个图片加载框保留为未连接的中性色块预览，可按[素材安装说明](../README.md#install-fixture-inputs)安装已有示例文件。真正的生成参考图来自 Workspace 素材选择，预览框不会替你绑定。

## 首段

1. 打开 [start.json](start.json)，选中的是空白 Shot 1。
2. 配置写作模型连接，上传并描述自己的素材，为当前镜头选择**两张有序参考图**。参考图数量改变时，相应调整编码器接线。
3. 填写镜头描述，编写六段式 H3 提示词，检查并接受。空提示词会阻止生成。
4. 镜头尺寸与原画布控件保持一致：默认 1344×768、24 fps；5 秒采样预算取整为 124 输入帧。
5. 生成。首段前片来源断开，Save Latent 为槽位 1，保存在 `output/shot_workspace_examples/pika-motion-context/latents/`。

## 续段

1. 保存／导出填写好的 Workspace。打开 [continue.json](continue.json)，导入该 Workspace 并选择 Shot 2；也可在空白续段模板里绑定相同素材并重新填写内容。**两份 JSON 不会自动同步已填写内容。**
2. 描述接着发生的动作，编写并接受新提示词；前后分辨率必须相同。
3. 确认 Load Latent 路径 `shot_workspace_examples/pika-motion-context/latents`，索引 **Load 1／Save 2**。缓存位于运行 ComfyUI 的机器。
4. 生成：`Load Latent → Shot Standard Media Outputs.context_latent → Motion Context` 携带前段音视频。新编码器 latent 仍接采样器，Motion Context 输出接 guider conditioning。
5. 视频保存和 latent 保存都要执行。继续时明确选择镜头，手动改为 Load 2／Save 3、3／4……本模板不自动排队或递增索引。新链用新缓存前缀；重跑同一槽位会替换该缓存。

已安装版本的 context-only 缓存不要直接接普通 VAE 解码，沿用采样器解码输出。这里必须是兼容的 H3 联合音视频 latent，不能换成任意 LATENT 或 MP4 路径。

## 时长与验证范围

画面上下文为 22 帧，音频为独立的 18 帧等效窗口。输出同步裁掉重复的 22 帧头部，并使音频长度匹配画面。默认首段交付 124 帧／5.1667 秒，续段交付 102 新帧／4.25 秒。5 秒表示裁剪前采样预算。

首段故意不连接前片：Workspace media 的空可选输出会产生 ExecutionBlocker，单靠 Load 0 不能绕过；先成功保存首段，再启用续接。

私有源样片已实际生成两段，通过完整音视频解码及前端检查，合计 226 帧。公开空白模板检查了连线、内容清理、原节点几何布局和空提示词阻断；**不宣称空白公开文件本身已 GPU 出片**。见 [VERIFICATION.json](VERIFICATION.json)。

来源为 [Comfy-Org 的 Pika H3 Flex 官方模板](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_pika_h3_flex_ref2va.json)，保留[原许可文本](LICENSE.Pika-template.MIT.txt)。不附带社区实现代码或权重。这是 ComfyUI 示例，不是 Director Studio 的 native-latent profile。
