# ComfyUI Shot Workspace

Prepare references, refine shot descriptions and write H3 video prompts inside ComfyUI. Connect **Workflow Interface** to your existing generation workflow; that workflow continues to own models, context, sampling and decoding.

**Experimental release · 0.1.0.** Python 3.10+. [中文说明](README.zh-CN.md) · [Examples](examples/README.md) · [Connection guide](docs/WORKFLOW_INTERFACE.md)

![Shot Workspace inside the ComfyUI canvas](docs/images/workspace.png)

## Install

Copy or clone this repository into `ComfyUI/custom_nodes/ComfyUI-ShotWorkspace`. Its `__init__.py` must sit directly inside that folder.

For a Git installation, run from your ComfyUI directory using its Python environment. If you already copied the ZIP, skip the clone command:

```sh
git clone https://github.com/ai2764/ComfyUI-ShotWorkspace.git custom_nodes/ComfyUI-ShotWorkspace
python -m pip install -r custom_nodes/ComfyUI-ShotWorkspace/requirements.txt
```

Restart ComfyUI and refresh the browser. Add **Shot Workspace (prototype)** from the Shot Workspace category. This is a custom node, not a ComfyUI installation. PyTorch and ComfyUI come from your existing installation; no model weights are bundled.

## Prepare a shot

1. Under **LLM connection**, enter an OpenAI-compatible URL and writing/vision model names. Start the model server separately, then click **Test connection** for real text and image requests.
2. Upload separate character, prop and scene assets. **Analyse image** produces an editable description; **Use description** saves it.
3. Select current-shot references in Picture order. Enter a description, refine it, then write and review the prompt. These three operations show separate elapsed times.
4. Create **Workflow Interface** and connect prompt and ordered images to the receiving workflow. Connect a sampler and video saver before **Generate this shot**.

Examples include an authored prompt and neutral fixtures, so their generation path can be explored without first connecting an LLM. Changing shot/reference content makes a prompt stale; rewrite it or review and accept a current prompt.

Configure an API key **environment variable name**, never the secret itself. **Unload LLM before generation** is off by default; enabling it needs a provider-specific, same-origin unload URL. OpenAI-compatible inference does not standardize unloading.

## Example workflows

| Workflow | Purpose | Origin |
| --- | --- | --- |
| [Motion Context video](examples/verified/01-motion-context-video.json) | Previous VIDEO → components → context frames/audio | Compact validated integration from a Comfy-Org H3 template and NikoDemon80's nodes |
| [MultiRef latent context](examples/verified/02-multiref-latent-context.json) | Native latent chain; existing decode → standard VIDEO | seitanism's complete AV Extension canvas: 102 original nodes, 20 groups, plus 6 interface nodes |
| [Native H3 latent](examples/verified/03-motion-context-native-latent.json) | Native AV latent save/load handoff | Supplement to the Motion Context example |

[Install fixture inputs and follow setup](examples/README.md) before running. These graphs derive from completed local video runs; private media and configuration were replaced for redistribution. The public fixtures were then GPU-rendered through all three routes, including a native-latent first clip and continuation. Small output clips and hashes are included in `examples/results/`. See [verification scope](examples/VERIFICATION.md).

The compact Motion Context integration is **not** the author's full v0.7 graph. The [unchanged original](examples/upstream/motion-context/H3-Motion-Context-v0.7.json) and [original-layout connection reference](examples/reference/motion-context-original-connected.json) are provided separately. The latter is not a completed full-v0.7 inference claim.

## Boundaries

- One active shot runs per queue; there is no full-sequence orchestration.
- Select predecessors explicitly. Output previews do not automatically feed the next shot; no self-feedback graph loop is provided.
- Different LATENT formats are not interchangeable. Reuse the compatible native decoder and package images/audio as VIDEO across workflow boundaries.
- Writing currently binds images. Advanced AUDIO/VIDEO/LATENT ports pass explicit media through; they do not automatically add media to LLM prompts.
- Sampling duration precedes context trimming. H3 input frames follow the `17k+5` grid at 24 fps; delivered video can be shorter.
- Workflows save authoring data, filenames and server URLs; image bytes stay in ComfyUI's input directory. Review before sharing.
- Routes rely on ComfyUI's access control; this node does not add authentication to a publicly exposed server.

## Development

```sh
python -m pip install -r requirements.txt
python -X utf8 -m unittest discover -s tests -v
node --test tests/uuid.test.cjs tests/default-config.test.cjs
```

Node.js 22+ is needed for JavaScript tests only. Native Torch tests skip outside a ComfyUI Torch environment. Minimal pinned JSON fixtures keep unit tests independent of private workspaces, GPU models and external APIs.

## License and credits

Original implementation, frontend and application authoring rules: [MIT](LICENSE). Upstream JSON and derived examples retain their original licenses, not the root MIT license. See [third-party notices](THIRD_PARTY_NOTICES.md).

Thanks to **NikoDemon80**, **seitanism**, **Comfy-Org**, **Zironic/H3-Optimizations**, and **VideoHelperSuite**. No community Python implementation or model weights are bundled.
