# Installation and first run

[中文](INSTALL.zh-CN.md) · [README](../README.md) · [Example workflows](../examples/README.md)

## What you need

| Component | Needed for | Setup |
| --- | --- | --- |
| Working ComfyUI, Python 3.10+ | Loading the node and editor | Use your existing ComfyUI installation and its Python environment |
| `aiohttp>=3.9`, `Pillow>=10` | This node's backend | Install this repository's `requirements.txt` as shown below |
| OpenAI-compatible chat-completions service | Analyse image, Refine description, Write prompt | Start separately; image analysis needs a vision-capable model |
| H3-capable ComfyUI, compatible model weights and receiving workflow's nodes | Generating video | Follow the [example setup](../examples/README.md) and the relevant upstream model/node instructions |

Installing this package does not download an LLM or H3 weights. You can open the editor without a model server. The bundled examples contain accepted prompts for inspecting/testing the video route without an LLM; editing those inputs makes the prompt stale.

## 1. Install the node

Choose **one** method. Close ComfyUI before installing, then restart it normally afterward. Git commands need [Git](https://git-scm.com/downloads). If the target folder already exists, use the update instructions instead of cloning over it.

### Windows Portable

Open PowerShell in `ComfyUI_windows_portable`, beside `python_embeded` and `ComfyUI`. Run:

```powershell
git clone https://github.com/ai2764/ComfyUI-ShotWorkspace.git .\ComfyUI\custom_nodes\ComfyUI-ShotWorkspace
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\ComfyUI-ShotWorkspace\requirements.txt
```

Use the bundled `python_embeded\python.exe` even if another Python is installed. Start ComfyUI with your usual launcher after installation.

### Manual installation: Linux, macOS, Windows venv or Conda

Activate the **same environment you use to start ComfyUI**, then open a terminal in the ComfyUI folder containing `main.py` and `custom_nodes`:

```sh
git clone https://github.com/ai2764/ComfyUI-ShotWorkspace.git custom_nodes/ComfyUI-ShotWorkspace
python -m pip install -r custom_nodes/ComfyUI-ShotWorkspace/requirements.txt
```

For a typical `.venv`, activation is `source .venv/bin/activate` on Linux/macOS or `.\.venv\Scripts\Activate.ps1` in Windows PowerShell. For Conda, use `conda activate YOUR_COMFYUI_ENV` with your actual environment name. Do not create a second environment just for this node. To inspect the selected interpreter:

```sh
python -c "import sys; print(sys.executable)"
```

### ComfyUI Desktop

Use Desktop's own terminal and actual `custom_nodes` directory. Do not edit the application's packaged program files or use an unrelated system Python. Desktop's storage path can differ from a manual ComfyUI checkout; locate it from your Desktop installation/startup information.

Clone or extract the repository into that `custom_nodes` directory. In the Desktop terminal with its Python environment active, install dependencies using the actual absolute path:

```sh
python -m pip install -r "/actual/path/to/custom_nodes/ComfyUI-ShotWorkspace/requirements.txt"
```

Replace the example path. If using Manager, install through it when your version permits this repository, then restart. A Manager search result or Git-URL installation option is not required by this guide; availability and security settings vary. See [ComfyUI's official custom-node installation guide](https://docs.comfy.org/basic-concepts/custom-nodes) for your installation type.

### ZIP installation without Git

1. On the repository page choose **Code → Download ZIP** and extract it.
2. Move the extracted package into your actual `ComfyUI/custom_nodes` folder and name the package folder `ComfyUI-ShotWorkspace`.
3. Check the structure below. Avoid `ComfyUI-ShotWorkspace/ComfyUI-ShotWorkspace-main/__init__.py` or duplicate copies of the package.
4. Skip `git clone` and run the dependency command for your installation type above.

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

### Verify installation

Restart the ComfyUI backend, then refresh its browser tab (Ctrl+F5 / Cmd+Shift+R if the editor is cached). Double-click an empty canvas area and search **Shot Workspace (prototype)** under **Shot Workspace**. Opening it should show the Shot workspace editor. **Workflow Interface** and **Shot Standard Media Outputs** are also supplied by this package.

## 2. Connect your LLM

Start your model server separately. It must support OpenAI-compatible **`/chat/completions`** requests; image analysis also requires image input. No particular model brand is required.

In **LLM connection**, fill:

| Field | Example / meaning |
| --- | --- |
| OpenAI-compatible URL | `http://127.0.0.1:1234/v1` for a server configured on port 1234; Ollama's default compatible endpoint is `http://127.0.0.1:11434/v1` |
| Writing model | The exact served model ID from your provider/server, not an arbitrary display name |
| Vision model | A served model accepting images; the same ID can serve both roles if that model supports both |
| API key environment variable | Leave blank for a server with no authentication; otherwise enter a variable name such as `SHOT_WORKSPACE_API_KEY` |

Ports above are examples. Include `/v1` when required by the provider; do not append `/chat/completions`, because the node appends it. Requests originate from the **ComfyUI backend**, so `127.0.0.1` refers to the machine/container running ComfyUI, not necessarily your browser's machine. Both roles currently share the configured base URL.

If authentication is required, define the variable in the environment that launches ComfyUI **before starting it**, then enter only its name in the editor. Do not paste a secret into the variable-name field or a shared workflow. A running Desktop process must also inherit the variable; setting it in an unrelated terminal will not update that process.

Click **Test connection**. It performs real requests: a text JSON probe and a blue-image vision probe. Both need to pass. This checks the two LLM roles without needing any uploaded references or connected generation workflow; it does not test H3 sampling.

The model server controls context capacity. **Unload LLM before generation** is off by default; leave it off for initial setup. Enabling it requires a working provider-specific unload URL on the same origin as the LLM endpoint. A standard OpenAI-compatible URL alone does not provide unloading.

## 3. Prepare your first shot

1. Upload separate character, prop and scene images into the asset library.
2. Click **Analyse image**, review the proposed text, then **Use description** to save it. You can also write a description manually.
3. Select the current shot's references in the intended **Picture 1, Picture 2, …** order. Reference type and binding notes are not required user inputs.
4. Enter a rough shot idea, use **Refine description**, then **Write prompt** and review the result. Image analysis, refinement and prompt writing each show their own elapsed time.
5. Click **Workflow interface ↗** to locate or add the interface node. Follow the [connection guide](WORKFLOW_INTERFACE.md) to wire its prompt and ordered images into the receiving workflow. Models, sampler, decoder and video saver remain in that workflow.
6. With a current accepted prompt and a connected output branch, click **Generate this shot**. A standalone editor cannot generate video until a receiving workflow is connected.

Save the ComfyUI workflow to retain your shot data. Reference image bytes stay in ComfyUI's input directory; sending the JSON alone does not send those images.

## 4. Run the first example

Start with [01 — Motion Context with VIDEO](../examples/README.md#01--motion-context-with-video). It is the compact integration; the separate original-layout reference graph has additional dependencies.

1. Install [NikoDemon80's Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) and [H3-Optimizations](https://github.com/Zironic/H3-Optimizations), following their dependency instructions in ComfyUI's Python environment. Restart afterward. Use an H3-capable ComfyUI build.
2. Install this repository's bundled inputs. **Windows Portable, from the portable root:**

   ```powershell
   .\python_embeded\python.exe .\ComfyUI\custom_nodes\ComfyUI-ShotWorkspace\tools\install_example_inputs.py --input-dir .\ComfyUI\input
   ```

   **Manual/Desktop, from the installed node repository with ComfyUI's environment active:**

   ```sh
   python tools/install_example_inputs.py --input-dir "/actual/path/to/ComfyUI/input"
   ```

   Pass your existing input directory. The script copies five fixture files and refuses to overwrite different existing files; it does not install nodes or weights.
3. Drag `examples/verified/01-motion-context-video.json` from the installed repository onto the ComfyUI canvas, or use ComfyUI's workflow Open command.
4. Resolve any missing node types, then select your installed compatible H3 diffusion, text encoder, video VAE and audio VAE in the loaders. Model filenames in the example are not downloaded automatically. Follow the upstream model instructions for correct locations and a configuration that fits your GPU.
5. Confirm the previous-video loader selects `shot-workspace-example-previous.mp4`; refresh its selector if needed. The example contains an accepted prompt: keep its authoring inputs unchanged for a first generation test without an LLM.
6. Queue the graph and inspect the video saver/result. Installing the editor or passing Test connection alone is not a successful video test.

For MultiRef and native-latent continuation, continue with the [example-specific instructions](../examples/README.md). Original Motion Context and the MultiRef fork can register overlapping node classes; use separate installations/profiles when needed. Previous outputs are selected explicitly, not automatically looped back.

## Update

For a Git installation, open a terminal in `custom_nodes/ComfyUI-ShotWorkspace`:

```sh
git pull --ff-only
```

Re-run the dependency command for your installation type, restart ComfyUI and refresh the browser. Preserve local changes if Git reports a conflict. For ZIP installations, back up your changes and replace the package with the new extracted copy; do not keep two enabled copies. Your image inputs and saved workflows remain outside the package folder.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Shot Workspace missing / `IMPORT FAILED` | Check the backend startup traceback, direct `__init__.py` placement, Python 3.10+, and that this is the ComfyUI installation you actually launched. Restart the backend, not just the browser. |
| Missing `aiohttp` / `PIL` | Re-run `requirements.txt` installation with ComfyUI's actual Python. `PIL` is supplied by Pillow. Portable users must use `python_embeded\python.exe`. |
| Node exists but editor is blank or old | Hard-refresh the browser after restarting. Check the browser console and backend log if it persists; remove duplicate enabled package copies. |
| Test connection refused / timed out / 404 | Check the model server is running, backend network reachability, port and API prefix. The base URL should not end in `/chat/completions`. Remote/container ComfyUI cannot use your laptop's `127.0.0.1`. |
| Authentication / model-not-found error | Check the exact served model ID and that the ComfyUI process inherited the named API-key variable. |
| Text succeeds, vision fails | The vision role must accept actual images; a text-only model or endpoint is insufficient. Read the provider error shown by the test. |
| Missing nodes / models when opening an example | Install the dependencies for that specific example and select existing compatible weights in its loaders; the node package includes neither. |
| Generate reports no output branch / stale prompt | Connect a downstream generation-and-save branch. After changing references, descriptions or shot settings, rewrite or review and accept the prompt. |
| LLM unload stops generation | Turn the optional checkbox off, or configure and test the provider-specific same-origin unload endpoint. |
| Out of GPU memory | Follow the receiving workflow's memory/model guidance and use models that fit your hardware. If an LLM occupies the same GPU, unload it through your server or configure the optional unload feature. No universal VRAM minimum is claimed. |
| Continuation does not use the previous shot | Select the intended previous VIDEO or compatible native LATENT explicitly and preserve the receiving workflow's context/trim connections. See the connection guide; filenames and arbitrary latent formats are not VIDEO. |

For a reproducible problem, [open an issue](https://github.com/ai2764/ComfyUI-ShotWorkspace/issues) with your OS, ComfyUI installation type/version, node commit, failing operation and relevant traceback. Remove API keys and private media/configuration before attaching logs or workflows.
