"""Serializable authoring contract. No ComfyUI, tensors, model calls or secrets."""
import copy
import hashlib
import json
import math
import re
from urllib.parse import urlparse

SECTION_KEYS = ("subject_definitions", "summary", "retention_analysis", "detailed_description",
                "overall_soundscape", "non_diegetic_music")
SCHEMA = "shot-workspace/1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def make_shot(workspace_json):
    data = json.loads(workspace_json)
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported workspace version; expected version 1.")
    shots = data.get("shots", [])
    ids = [s["id"] for s in shots]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate shot ID.")
    source = next((s for s in shots if s["id"] == data.get("active_shot_id")), None)
    if source is None:
        raise ValueError("Select an active shot in the workspace.")
    assets = {a["id"]: a for a in data.get("assets", [])}
    if len(assets) != len(data.get("assets", [])):
        raise ValueError("Duplicate asset ID.")
    refs, used = [], set()
    for index, ref in enumerate(source.get("refs", []), 1):
        asset_id = ref["asset_id"]
        if asset_id in used:
            raise ValueError("Duplicate reference in this shot.")
        if asset_id not in assets:
            raise ValueError("A selected reference asset is missing.")
        used.add(asset_id)
        asset = assets[asset_id]
        refs.append({"picture_index": index, "asset_id": asset_id, "name": asset.get("name", ""),
                     "image": asset.get("image", ""), "description": asset.get("description", ""),
                     "role": ref.get("role", "reference"), "binding_notes": ref.get("notes", "")})
    if len(refs) > 9:
        raise ValueError("H3 supports at most 9 image references.")
    duration = float(source.get("duration_s", 5))
    if not math.isfinite(duration) or not 0 < duration <= 120:
        raise ValueError("Duration must be finite and between 0 and 120 seconds.")
    width, height = source.get("width", 704), source.get("height", 480)
    if any(type(v) is not int or not 32 <= v <= 16384 or v % 32 for v in (width, height)):
        raise ValueError("Width and height must be a multiple of 32, from 32 to 16384.")
    requested_frames = max(5, math.ceil(duration * 24))
    length = requested_frames + (5 - requested_frames) % 17
    inputs = {"title": str(source.get("title", "")), "brief": str(source.get("brief", "")),
              "duration_s": duration, "width": width, "height": height, "references": refs,
              "continuity": copy.deepcopy(source.get("continuity", {"mode": "off"}))}
    if source.get("dialogue"):
        inputs['dialogue'] = source['dialogue']
    sections = source.get("prompt_sections", {})
    if not isinstance(sections, dict):
        raise ValueError("prompt_sections must be an object.")
    basis = source.get("prompt_basis")
    stale = bool(sections and (source.get("prompt_editor_dirty") or basis is None or basis != inputs))
    if sections and not stale:
        if set(sections) != set(SECTION_KEYS) or any(not isinstance(sections[k], str) or not sections[k].strip() for k in SECTION_KEYS):
            raise ValueError("Provide all six nonempty H3 sections.")
        text = "\n".join(sections.values())
        found = {int(n) for n in re.findall(r"<Picture\s+(\d+)>", text)}
        expected = set(range(1, len(refs) + 1))
        if found - expected:
            raise ValueError("Prompt contains an unselected Picture tag.")
        if expected - found:
            raise ValueError("Prompt must mention every selected <Picture N>.")
        if re.search(r"<(?:Audio|Video)\s+\d+>", text):
            raise ValueError("This prototype binds images only; Audio/Video tags need a dedicated adapter.")
    return {"schema": SCHEMA, "shot_id": source["id"], "revision": digest(inputs), "inputs": inputs,
            **copy.deepcopy(inputs), "fps": 24, "length": length, "sampling_duration_s": length / 24,
            "duration_semantics": "sampling_input_before_workflow_trim", "actual_duration_s": None,
            "prompt_sections": copy.deepcopy(sections), "prompt_ready": bool(sections) and not stale,
            "prompt_stale": stale, "prompt_origin": source.get('prompt_origin', 'manual') if sections else "none"}


def input_signature(shot):
    return digest(shot["inputs"])


def require_shot(shot):
    if not isinstance(shot, dict) or shot.get("schema") != SCHEMA:
        raise ValueError("Expected a shot-workspace/1 SHOT bundle.")


def compose_prompt(shot):
    require_shot(shot)
    if shot["prompt_stale"]:
        raise ValueError("Prompt is stale. Review and accept it again for the current shot.")
    sections = shot["prompt_sections"]
    return "\n".join(f"{key}:\n{sections[key]}" for key in SECTION_KEYS) if sections else ""


def llm_config(base_url, text_model, vision_model="", api_key_env="", timeout_s=120):
    url = urlparse(base_url)
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Use an http(s) OpenAI-compatible base URL without credentials or query parameters.")
    if api_key_env and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
        raise ValueError("api_key_env must be an environment variable name, never an API key.")
    return {"schema": "shot-workspace-llm/1", "base_url": base_url.rstrip("/"),
            "text_model": text_model, "vision_model": vision_model, "api_key_env": api_key_env,
            "timeout_s": int(timeout_s)}


def llm_request(shot, config, operation):
    require_shot(shot)
    if operation not in {"refine_description", "write_prompt"}:
        raise ValueError("Unsupported authoring operation.")
    if not config["text_model"].strip():
        raise ValueError("Set the text model name in LLM Config.")
    payload = {"shot": {k: shot[k] for k in ("shot_id", "title", "brief", "duration_s")},
               "references": [{k: r[k] for k in ("picture_index", "name", "role", "description", "binding_notes")}
                              for r in shot["references"]], "continuity": shot["continuity"]}
    system = ('Refine one editable shot description. Return a JSON object with exactly one nonempty string field: "description". '
              "Preserve the user's intent, duration and explicit dialogue. "
              if operation == "refine_description" else
              "Write one H3 prompt as a JSON object containing exactly these nonempty string fields: " + ", ".join(SECTION_KEYS) + ". Use every selected <Picture N> and no other reference tags. ")
    system += ("Use the supplied saved reference descriptions and binding notes as data. "
               "Do not claim to have seen image pixels or a previous generated video's ending. "
               "Do not select assets, invent dialogue or execute generation.")
    return {"preview_only": True, "operation": operation, "shot_id": shot["shot_id"], "revision": shot["revision"],
            "method": "POST", "url": config["base_url"].rstrip("/") + "/chat/completions",
            "auth_env": config.get("api_key_env", ""), "timeout_s": config.get("timeout_s", 120),
            "body": {"model": config["text_model"], "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                     "temperature": 0.2, "stream": False, "response_format": {"type": "json_object"}}}
