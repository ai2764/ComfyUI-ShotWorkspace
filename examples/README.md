# Example workflows

## Pika H3 Flex + Motion Context — blank templates

[Start / continuation setup](pika-motion-context/README.md) · [中文](pika-motion-context/README.zh-CN.md). These preserve the official Pika canvas and add Workspace/native AV latent continuation. They deliberately contain no story, dialogue, prompts or selected assets: author your own content before generating. Their private source pair ran successfully; these blank files have structural/content checks and are separate from the three public-fixture GPU reruns below.

Bundled reference images and the three-second video are procedural color blocks for testing media connections, not AI-generated results. Replace them with your material for creative work.

New installation? Follow the [installation and first-run guide](../docs/INSTALL.md) ([中文](../docs/INSTALL.zh-CN.md)) first. It includes Windows Portable commands, Desktop/environment selection, LLM setup and a complete first run of example 01. The instructions below cover each workflow's additional dependencies and connections.

## Install fixture inputs

From this repository directory, pass your actual ComfyUI input directory:

```sh
python tools/install_example_inputs.py --input-dir /path/to/ComfyUI/input
```

This copies five namespaced files: three PNGs, one MP4 and one WAV. Different existing files are never overwritten. No models or nodes are downloaded. Import the example JSON after copying; refresh stale file selectors.

Choose installed, compatible H3 diffusion/text/video-VAE/audio-VAE models in the existing loaders. Recorded filenames are examples, not included weights. The model set must fit your hardware.

## 01 — Motion Context with VIDEO

Install NikoDemon80's [Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) and [H3-Optimizations](https://github.com/Zironic/H3-Optimizations), plus this package and H3-capable ComfyUI.

1. Open `verified/01-motion-context-video.json`.
2. Inspect the previous-video loader: it explicitly selects `shot-workspace-example-previous.mp4`.
3. `Load Video → Get Video Components → Shot Standard Media Outputs` supplies frames/audio to Motion Context. The native latent input is disconnected for this route.
4. Workflow Interface supplies the prompt and ordered images to the native H3 encoder.
5. Generate and inspect the connected video saver. Use one predecessor source at a time.

This is a compact integration, not a rearranged copy of the author's full v0.7 graph. `reference/motion-context-original-connected.json` separately retains that complete original layout. Its additional dependencies and full inference are not certified by the compact example's tests.

## 02 — MultiRef native latent context and VIDEO output

Use seitanism's [MultiRef fork](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef) and [VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite). Original Motion Context and its fork may register overlapping classes; use separate ComfyUI installations/profiles when needed.

1. Open `verified/02-multiref-latent-context.json`. Its 102 original nodes, 20 groups and layout remain, with six interface nodes added around them.
2. The controller selects **Existing Video**, **one extension**. The original loader selects the bundled three-second clip at 24 fps, capped at 72 frames.
3. Inspect the receiving encoder first: `Workflow Interface.prompt → encoder.prompt`, and `image_1/2/3 → ref_image_0/1/2`. Native image indices start at zero.
4. Preserve the native context stage, protected 39-frame prefix, masks, sampler and decoder. Later extension stages retain their original prompts/timing and are inactive here.
5. Reuse the existing video/audio decoder outputs. Create Video assembles them at 24 fps. Its VIDEO connects through our media adapter to a stock video saver.
6. VHS Video Combine returns **filenames**, not VIDEO. Do not connect that output to a VIDEO input. If another workflow already outputs VIDEO, use it directly.
7. Generate one extension and play it. The next predecessor is selected manually; no output-to-input feedback loop is implied.

The original image loaders remain for familiarity; the active encoder receives the selected shot references, so the same images do not need uploading twice. Nothing is automatically retrieved from a knowledge library.

## 03 — Native H3 AV LATENT supplement

Use original Motion Context as in example 01. Both ends need its compatible native H3 AV format, not an arbitrary latent.

1. First open `helpers/native-latent-bootstrap.json`. Its Load Latent uses slot 0 (no prior file), connected directly to the native Motion Context input; Save Latent uses slot 1.
2. Generate the first clip. It saves `output/shot_workspace_examples/native-latent/clip_00001.safetensors`.
3. Open `verified/03-motion-context-native-latent.json` for continuation. It loads slot 1 from `shot_workspace_examples/native-latent` through our media adapter and saves slot 2. Update the shot/prompt as needed and generate.
4. Select the specific accepted source slot for each run; changing shots does not automatically choose it. Keep unrelated shots in different folders.

Slot semantics belong to Motion Context. A slot-zero empty source must bypass our media adapter: absent media outputs intentionally block dependent execution. Its native AV context cache is not a stock VAEDecode input. Reuse the compatible decoder or completed VIDEO to cross into another latent system.

## Sources and checks

`verified/DEPENDENCIES.json` lists node types and installed module origins. Note/Reroute in the original MultiRef graph are frontend-only. [VERIFICATION.md](VERIFICATION.md) separates completed inference from public-template checks. `verified/PRESERVATION.json` records unchanged positions, sizes, groups and links.
