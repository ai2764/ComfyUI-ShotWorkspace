# Pika H3 Flex + Shot Workspace + Motion Context

[中文说明](README.zh-CN.md)

These are **blank authoring templates**. Test story, dialogue, prompts, character references and personal configuration have been removed. All 22 original Pika node positions/sizes and original groups are retained; Workspace and continuation helpers sit outside the official canvas.

## Requirements

Use H3/Pika-capable ComfyUI, this node package, and [H3 Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) with compatible Load/Save Latent and Trim nodes. Source runs used ComfyUI 0.38.0, FP16 video VAE, FP32 audio VAE, Pika H3 Flex reference adapter at strength 1, and LCM six-step sigmas. Select compatible locally installed weights in the existing loaders; weights are not included.

The two original image-loader boxes remain as disconnected previews of existing procedural fixtures. Install them with [the fixture installer](../README.md#install-fixture-inputs), if desired. Active encoder references come from Workspace selections, not these preview boxes.

## Start

1. Open [start.json](start.json). It selects blank **Shot 1**.
2. Configure your writing-model connection. Upload/describe your assets and select **two ordered reference images**. Change the encoder reference wiring if using a different image count.
3. Enter the shot description, write a six-section prompt and review/accept it. An empty prompt deliberately blocks generation.
4. Keep authored dimensions aligned with the original canvas controls: default 1344×768, 24 fps, five-second sampling budget rounded to 124 input frames.
5. Generate. Previous context is disconnected for this first run. Save Latent uses slot 1, under `output/shot_workspace_examples/pika-motion-context/latents/`.

## Continue

1. Export/save the authored Workspace. Open [continue.json](continue.json), import that Workspace and select **Shot 2**, or populate the blank continuation template with the same references and a new accepted prompt. The two JSON files do not automatically share edits.
2. Describe the continued action and accept its prompt. Source and target dimensions must match.
3. Confirm Load Latent folder `shot_workspace_examples/pika-motion-context/latents`, **Load 1 / Save 2**. The cache resides on the ComfyUI host.
4. Generate. `Load Latent → Shot Standard Media Outputs.context_latent → Motion Context` carries previous picture and sound. The fresh encoder latent still feeds the sampler; Motion Context modifies guider conditioning.
5. Both SaveVideo and SaveLatent must execute. For further shots explicitly advance to Load 2 / Save 3, then 3 / 4. Shot selection does not advance indices or queue a sequence. Use a unique prefix for a new chain; rerunning a numbered slot replaces its cache.

The installed loader's context-only cache is not an ordinary decoder input. Use the sampler's existing decoders. Only compatible native H3 AV latent works here, not an arbitrary latent or MP4 filename.

## Timing / bootstrap

Video context is 22 frames; audio context is an independent 18-frame-equivalent tail. Trim removes the overlapping 22-frame head from picture and sound, then matches audio length to delivered picture. Default first delivery: 124 frames / 5.1667s. Continuation: 102 new frames / 4.25s. The five-second control is a sampling budget before context trim.

Start deliberately disconnects previous context: empty optional Workspace media outputs are ExecutionBlockers. Native Load index 0 alone does not bypass that media behavior. Enable the continuation route only after saving the predecessor cache.

## Verification / source

The private source pair completed generation, full audio/video decoding and frontend checks: 226 joined frames at 24 fps. Blank public templates are checked for valid links, content removal, original geometry and empty-prompt blocking; **the blank files are not claimed as GPU-rendered public outputs**. See [VERIFICATION.json](VERIFICATION.json).

Based on [Comfy-Org's Pika H3 Flex template](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_pika_h3_flex_ref2va.json); original attribution/license is in [LICENSE.Pika-template.MIT.txt](LICENSE.Pika-template.MIT.txt). No community Python implementation or weights are bundled. This is a ComfyUI example, not a Director Studio native-latent profile.
