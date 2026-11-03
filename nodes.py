"""ComfyUI boundary: authoring data, ordinary ports and an optional native H3 adapter."""
import hashlib
import json
from pathlib import Path

import folder_paths
import nodes as comfy_nodes
from comfy_execution.graph_utils import ExecutionBlocker

from .contract import make_shot, compose_prompt, require_shot, llm_config, llm_request

EMPTY_WORKSPACE = json.dumps({"version": 1, "assets": [], "shots": [{"id": "shot-1", "title": "Shot 1",
    "brief": "", "duration_s": 5, "width": 704, "height": 480, "refs": []}], "active_shot_id": "shot-1"})


def image_path(name):
    if not isinstance(name, str) or not name:
        raise ValueError("Upload or select an image for every bound reference.")
    path = Path(folder_paths.get_annotated_filepath(name)).resolve()
    roots = [Path(folder_paths.get_input_directory()).resolve(), Path(folder_paths.get_output_directory()).resolve(),
             Path(folder_paths.get_temp_directory()).resolve()]
    if not any(path.is_relative_to(root) for root in roots):
        raise ValueError("Reference images must be inside ComfyUI input, output or temp directories.")
    if not path.is_file():
        raise ValueError(f"Reference image is missing: {name}")
    return path


def load_reference(shot, picture_index):
    require_shot(shot)
    refs = shot["references"]
    if not 1 <= picture_index <= len(refs):
        raise ValueError(f"Picture {picture_index} is not selected in this shot.")
    ref = refs[picture_index - 1]
    path = image_path(ref["image"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("content_sha256"):
        raise ValueError("Reference bytes changed after the shot snapshot. Queue again to capture the new revision.")
    image, mask = comfy_nodes.LoadImage().load_image(ref["image"])
    return image[:1], ref


class ShotWorkspace:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"workspace_json": ("STRING", {"multiline": True, "default": EMPTY_WORKSPACE})}}

    RETURN_TYPES = ("SHOT", "STRING", "FLOAT", "INT", "INT", "INT", "FLOAT", "STRING")
    RETURN_NAMES = ("shot", "prompt", "duration_s", "width", "height", "length", "fps", "snapshot_json")
    FUNCTION = "capture"
    CATEGORY = "Shot Workspace"
    DESCRIPTION = "Author multiple shots and a shared asset library. LLM authoring is explicit in the editor; queue captures only the active shot."

    @classmethod
    def IS_CHANGED(cls, workspace_json):
        shot = make_shot(workspace_json)
        expected = json.loads(workspace_json).get('_queued_media_hashes')
        hashes = tuple(hashlib.sha256(image_path(r["image"]).read_bytes()).hexdigest() for r in shot["references"])
        if expected is not None and any(expected.get(str(i + 1)) != value for i, value in enumerate(hashes)):
            raise ValueError('Reference bytes changed after this shot was queued. Queue a new snapshot.')
        return hashes

    def capture(self, workspace_json):
        shot = make_shot(workspace_json)
        hashes = self.IS_CHANGED(workspace_json)
        for ref, value in zip(shot["references"], hashes):
            ref["content_sha256"] = value
        # Bytes are execution provenance, separate from the author's prompt basis.
        shot["revision"] = hashlib.sha256(json.dumps(shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        prompt = compose_prompt(shot) if shot["prompt_ready"] else ExecutionBlocker(
            "Review and accept a current six-section prompt in Shot Workspace before generating.")
        return shot, prompt, shot["duration_s"], shot["width"], shot["height"], shot["length"], float(shot["fps"]), json.dumps(shot, ensure_ascii=False, indent=2)


class ShotWorkspaceReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"shot": ("SHOT",), "picture_index": ("INT", {"default": 1, "min": 1, "max": 9})}}

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("image", "description", "binding_notes", "picture_tag")
    FUNCTION = "extract"
    CATEGORY = "Shot Workspace"

    def extract(self, shot, picture_index):
        image, ref = load_reference(shot, picture_index)
        return image, ref["description"], ref["binding_notes"], f"<Picture {picture_index}>"


class ShotWorkspaceMedia:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"shot": ("SHOT",)}, "optional": {
            **{f"audio_{i}": ("AUDIO",) for i in range(1, 4)}, "video": ("VIDEO",),
            "video_frames": ("IMAGE",), "video_audio": ("AUDIO",), "context_latent": ("LATENT",)}}

    RETURN_TYPES = ("IMAGE",) * 9 + ("AUDIO",) * 3 + ("VIDEO", "IMAGE", "AUDIO", "LATENT")
    RETURN_NAMES = tuple(f"image_{i}" for i in range(1, 10)) + tuple(f"audio_{i}" for i in range(1, 4)) + (
        "video", "video_frames", "video_audio", "context_latent")
    FUNCTION = "unpack"
    CATEGORY = "Shot Workspace"
    DESCRIPTION = "Nine ordered Picture images plus explicit standard audio/video/context ports. External media is passed unchanged and is not automatically analysed or bound by the writer."

    def unpack(self, shot, audio_1=None, audio_2=None, audio_3=None, video=None, video_frames=None,
               video_audio=None, context_latent=None):
        require_shot(shot)
        images = [load_reference(shot, i + 1)[0] if i < len(shot["references"]) else ExecutionBlocker(None) for i in range(9)]
        extras = [audio_1, audio_2, audio_3, video, video_frames, video_audio, context_latent]
        return tuple(images + [v if v is not None else ExecutionBlocker(None) for v in extras])


class ShotWorkspaceInterface:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"shot": ("SHOT",)}}

    RETURN_TYPES = ("STRING", "FLOAT", "INT", "INT", "INT", "FLOAT") + ("IMAGE",) * 9
    RETURN_NAMES = ("prompt", "duration_s", "width", "height", "frame_count", "fps") + tuple(f"image_{i}" for i in range(1, 10))
    FUNCTION = "expose"
    CATEGORY = "Shot Workspace"
    DESCRIPTION = "Workflow connection boundary: standard prompt, canvas, input frames, fps and ordered Picture images. Connect only the ports your workflow needs. Sampling and continuation stay downstream."

    def expose(self, shot):
        require_shot(shot)
        prompt = compose_prompt(shot) if shot["prompt_ready"] else ExecutionBlocker(
            "Accept a current prompt in Shot Workspace before generating.")
        images = ShotWorkspaceMedia().unpack(shot)[:9]
        return (prompt, shot["duration_s"], shot["width"], shot["height"], shot["length"], float(shot["fps"]), *images)


class ShotWorkspaceH3Encode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"shot": ("SHOT",), "clip": ("CLIP",), "vae": ("VAE",), "audio_vae": ("VAE",),
                             "ref_image_size": (["match", "max"], {"default": "match"})}}

    RETURN_TYPES = ("CONDITIONING", "LATENT")
    RETURN_NAMES = ("positive", "latent")
    FUNCTION = "encode"
    CATEGORY = "Shot Workspace/adapters"
    DESCRIPTION = "Native H3 image Ref2AV adapter. Sampling, LoRA, continuation, decode and saving stay outside."

    def encode(self, shot, clip, vae, audio_vae, ref_image_size):
        require_shot(shot)
        if not shot["prompt_ready"]:
            raise ValueError("This shot has no current six-section prompt. Review and accept a manual prompt first.")
        if not shot["references"]:
            raise ValueError("Select at least one image reference for Ref2AV.")
        # Continuation intent is authoring context. The downstream graph owns actual anchors.
        from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo
        images = {f"ref_image_{i}": load_reference(shot, i + 1)[0] for i in range(len(shot["references"]))}
        result = MiniMaxH3ReferenceToVideo.execute(clip=clip, vae=vae, audio_vae=audio_vae,
            prompt=compose_prompt(shot), width=shot["width"], height=shot["height"], length=shot["length"],
            ref_image_size=ref_image_size, ref_images=images)
        return result[0], result[1]


class ShotWorkspaceLLMConfig:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"base_url": ("STRING", {"default": "http://127.0.0.1:1234/v1"}),
            "text_model": ("STRING", {"default": ""}), "vision_model": ("STRING", {"default": ""}),
            "api_key_env": ("STRING", {"default": ""}), "timeout_s": ("INT", {"default": 120, "min": 1, "max": 600})}}

    RETURN_TYPES = ("SW_LLM_CONFIG",)
    RETURN_NAMES = ("llm_config",)
    FUNCTION = "configure"
    CATEGORY = "Shot Workspace/LLM"
    DESCRIPTION = "OpenAI-compatible connection contract only. No network calls. Use a key environment variable name, never a secret."

    def configure(self, base_url, text_model, vision_model, api_key_env, timeout_s):
        return (llm_config(base_url, text_model, vision_model, api_key_env, timeout_s),)


class ShotWorkspaceLLMRequest:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"shot": ("SHOT",), "llm_config": ("SW_LLM_CONFIG",),
                             "operation": (["write_prompt", "refine_description"],)}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("request_json",)
    FUNCTION = "preview"
    CATEGORY = "Shot Workspace/LLM"
    OUTPUT_NODE = True
    DESCRIPTION = "Preview the future request and selected-reference context. Does not send it."

    def preview(self, shot, llm_config, operation):
        text = json.dumps(llm_request(shot, llm_config, operation), ensure_ascii=False, indent=2)
        return {"ui": {"text": [text]}, "result": (text,)}


class ShotWorkspaceH3AudioWindow:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'shot':('SHOT',),'av_latent':('LATENT',),'audio_vae':('VAE',)}}
    RETURN_TYPES=('LATENT',)
    RETURN_NAMES=('av_latent',)
    FUNCTION='apply'
    CATEGORY='Shot Workspace/Adapters'
    DESCRIPTION='Experimental native H3 joint-latent speech window. Holds prefix/tail at VAE-encoded silence during sampling; does not edit output audio. Requires native nested AV mask support.'
    def apply(self,shot,av_latent,audio_vae):
        from .authoring_rules import delivery_window,authored_dialogue
        from .h3_audio_window import mask_h3_audio
        require_shot(shot)
        window=delivery_window(shot)
        if not window or not authored_dialogue(shot):raise ValueError('Declare delivery timing and authored speech before using the H3 audio-window adapter.')
        if not shot['prompt_ready']:raise ValueError('Write a current prompt before sampling.')
        return (mask_h3_audio(av_latent,audio_vae,window),)

NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in (ShotWorkspace, ShotWorkspaceInterface, ShotWorkspaceReference, ShotWorkspaceMedia, ShotWorkspaceH3Encode,ShotWorkspaceH3AudioWindow,
                                                    ShotWorkspaceLLMConfig, ShotWorkspaceLLMRequest)}
NODE_DISPLAY_NAME_MAPPINGS = {"ShotWorkspace": "Shot Workspace (prototype)", "ShotWorkspaceReference": "Shot Reference",
    "ShotWorkspaceMedia": "Shot Standard Media Outputs",
    "ShotWorkspaceInterface": "Workflow Interface",
    "ShotWorkspaceH3AudioWindow": "H3 Sampling Audio Window (experimental)",
    "ShotWorkspaceH3Encode": "H3 Shot Encode (native)", "ShotWorkspaceLLMConfig": "Shot LLM Config (interface)",
    "ShotWorkspaceLLMRequest": "Shot LLM Request Preview (no call)"}
