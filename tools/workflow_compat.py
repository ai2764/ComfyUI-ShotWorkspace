"""Transform pinned public workflow JSON without importing community Python code.

These are connection/contract artifacts, not claims of successful model inference.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from contract import SECTION_KEYS, make_shot

SOURCES = ROOT / "tests" / "fixtures" / "upstream"
CASES = {
    "official": ("official", "templates/video_minimax_h3_r2v.json"),
    "motion-context": ("motion-context", "example_workflows/H3-Motion-Context-v0.7.json"),
    "multiref-av": ("multiref", "example_workflows/NEW - AV Extension.json"),
    "multiref-v2v": ("multiref", "example_workflows/NEW - V2V Latent Motion Transfer (with upscale and de-rope).json"),
    "continuum": ("continuum", "examples/workflows/MiniMax_H3_Continuum_V39_Reference_Inline.json"),
}


def port_compatible(source, target):
    return source == target or source in target.split(",") or target == "*" or source == "*"


class Graph:
    def __init__(self, data):
        self.data = data
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.added_links = []

    def input(self, node_id, name):
        return next(i for i in self.nodes[node_id].get("inputs", []) if i["name"] == name)

    def disconnect(self, node_id, name):
        target = self.input(node_id, name)
        link_id = target.get("link")
        if link_id is not None:
            link = next((l for l in self.data["links"] if l[0] == link_id), None)
            if link:
                source = self.nodes.get(link[1])
                if source:
                    output = source["outputs"][link[2]]
                    output["links"] = [i for i in output.get("links") or [] if i != link_id]
                self.data["links"] = [l for l in self.data["links"] if l[0] != link_id]
        target["link"] = None

    def connect(self, source_id, source_slot, target_id, name, target_type):
        node = self.nodes[target_id]
        if not any(i["name"] == name for i in node.get("inputs", [])):
            node.setdefault("inputs", []).append({"name": name, "type": target_type,
                "widget": {"name": name}, "link": None})
        self.disconnect(target_id, name)
        slot = next(i for i, value in enumerate(node["inputs"]) if value["name"] == name)
        source = self.nodes[source_id]["outputs"][source_slot]
        if not port_compatible(source["type"], target_type):
            raise ValueError(f"Cannot connect {source['type']} to {target_type}")
        link_id = max([self.data.get("last_link_id", 0)] + [l[0] for l in self.data["links"]]) + 1
        self.data["last_link_id"] = link_id
        node["inputs"][slot]["link"] = link_id
        source["links"] = (source.get("links") or []) + [link_id]
        link = [link_id, source_id, source_slot, target_id, slot, source["type"]]
        self.data["links"].append(link)
        self.added_links.append(link)

    def replace_fanout(self, source_id, source_slot, new_source, new_slot):
        edges = [l for l in self.data["links"] if l[1:3] == [source_id, source_slot]]
        for link in edges:
            target = self.nodes[link[3]]["inputs"][link[4]]
            self.connect(new_source, new_slot, link[3], target["name"], target["type"])

    def add(self, node):
        value = copy.deepcopy(node)
        value["id"] = max(self.nodes, default=0) + 1
        for port in value.get("inputs", []):
            port["link"] = None
        for port in value.get("outputs", []):
            port["links"] = []
        self.nodes[value["id"]] = value
        self.data["nodes"].append(value)
        self.data["last_node_id"] = value["id"]
        return value["id"]

    def issues(self):
        result = []
        seen = set()
        for edge in self.data["links"]:
            key, source_id, source_slot, target_id, target_slot, kind = edge
            if key in seen:
                result.append(f"duplicate link {key}")
            seen.add(key)
            if source_id not in self.nodes or target_id not in self.nodes:
                result.append(f"link {key}: missing endpoint")
                continue
            source = self.nodes[source_id].get("outputs", [])
            target = self.nodes[target_id].get("inputs", [])
            if source_slot >= len(source) or target_slot >= len(target):
                result.append(f"link {key}: missing slot")
                continue
            if target[target_slot].get("link") != key or key not in (source[source_slot].get("links") or []):
                result.append(f"link {key}: inconsistent backlink")
            if not port_compatible(source[source_slot]["type"], target[target_slot]["type"]):
                result.append(f"link {key}: type mismatch {source[source_slot]['type']} -> {target[target_slot]['type']}")
        return sorted(result)


def preserved_continuity_nodes(workflow):
    names = ("MotionContext", "MaskedContext", "H3V2VInit", "H3ExactRecover", "H3TimeSmear", "H3AudioSmear",
             "H3V2VGranular", "H3ContinuumAssemble", "MiniMaxH3SourceAudio", "MiniMaxH3StreamLiveExtension")
    return {n["id"]: n for n in workflow["nodes"] if any(key in n["type"] for key in names)}


def test_workspace():
    data = {"version": 1, "assets": [
        {"id": "compat-blue", "name": "Blue test panel", "image": "shot_workspace/compat_ref_1.png", "description": "A synthetic blue test panel."},
        {"id": "compat-red", "name": "Red test panel", "image": "shot_workspace/compat_ref_2.png", "description": "A synthetic red test panel."}],
        "shots": [{"id": "compat-shot", "title": "Compatibility test", "brief": "A slow camera move across a quiet room with blue and red panels.",
                   "duration_s": 5, "width": 704, "height": 480,
                   "refs": [{"asset_id": "compat-blue", "role": "scene", "notes": "Blue panel appearance only."},
                            {"asset_id": "compat-red", "role": "prop", "notes": "Red panel appearance only."}],
                   "prompt_sections": {
                       "subject_definitions": "<Picture 1> is the blue panel. <Picture 2> is the red panel.",
                       "summary": "A slow camera move across a quiet room.",
                       "retention_analysis": "Preserve the panels from <Picture 1> and <Picture 2>.",
                       "detailed_description": "The camera moves slowly across a quiet room, keeping the blue and red panels visible.",
                       "overall_soundscape": "Quiet room tone. No speech.", "non_diegetic_music": "None"}}], "active_shot_id": "compat-shot"}
    data["shots"][0]["prompt_basis"] = make_shot(json.dumps(data))["inputs"]
    return data


def inject_workspace(graph):
    template = json.loads((ROOT / "examples" / "interface-preview.json").read_text(encoding="utf-8"))
    node = next(n for n in template["nodes"] if n["type"] == "ShotWorkspace")
    node = copy.deepcopy(node)
    node["widgets_values"] = [json.dumps(test_workspace(), ensure_ascii=False)]
    x = min(n.get("pos", [0, 0])[0] for n in graph.nodes.values()) - 1150
    y = min(n.get("pos", [0, 0])[1] for n in graph.nodes.values())
    node["pos"] = [x, y]
    node["title"] = "Shot Workspace — compatibility fixture (replace synthetic assets)"
    workspace = graph.add(node)
    references = []
    for index in (1, 2):
        node = {"type": "ShotWorkspaceReference", "pos": [x + 830, y + 100 + 180 * index],
                "size": [290, 145], "flags": {}, "mode": 0, "order": 0,
                "inputs": [{"name": "shot", "type": "SHOT", "link": None}],
                "outputs": [{"name": name, "type": kind, "links": []} for name, kind in
                            [("image", "IMAGE"), ("description", "STRING"), ("binding_notes", "STRING"), ("picture_tag", "STRING")]],
                "properties": {"Node name for S&R": "ShotWorkspaceReference"}, "widgets_values": [index]}
        ref = graph.add(node)
        graph.connect(workspace, 0, ref, "shot", "SHOT")
        references.append(ref)
    return workspace, references


def bind_native_images(graph, node_id, references):
    for port in list(graph.nodes[node_id].get("inputs", [])):
        if port["name"].startswith("ref_images."):
            graph.disconnect(node_id, port["name"])
    for index, reference in enumerate(references):
        graph.connect(reference, 0, node_id, f"ref_images.ref_image_{index}", "IMAGE")


def build_case(case):
    slug, filename = CASES[case]
    original = json.loads((SOURCES / slug / "source" / filename).read_text(encoding="utf-8-sig"))
    workflow = copy.deepcopy(original)
    graph = Graph(workflow)
    baseline = set(graph.issues())
    workspace, references = inject_workspace(graph)
    profile = "active shot prompt + two independent images"
    warnings = []
    if case in {"official", "motion-context"}:
        target = next(n["id"] for n in workflow["nodes"] if n["type"] == "MiniMaxH3ReferenceToVideo")
        graph.connect(workspace, 1, target, "prompt", "STRING")
        bind_native_images(graph, target, references)
        if case == "motion-context":
            graph.replace_fanout(510, 0, workspace, 3)
            graph.replace_fanout(510, 1, workspace, 4)
            graph.replace_fanout(522, 0, workspace, 5)
            warnings.append("length is pre-trim H3 frames: a 22-frame context makes a 124-frame render deliver 102 new frames, not 5 seconds")
        else:
            for output, name in [(3, "width"), (4, "height"), (5, "length")]:
                graph.connect(workspace, output, target, name, "INT")
    elif case == "multiref-av":
        # Generated canvas is editable; existing-video canvas remains source-owned.
        graph.replace_fanout(1024, 0, workspace, 3)
        graph.replace_fanout(1024, 1, workspace, 4)
        graph.connect(workspace, 2, 102, "values.a", "FLOAT,INT,BOOLEAN")
        for node in list(workflow["nodes"]):
            if node["type"] == "MiniMaxH3ReferenceToVideo":
                bind_native_images(graph, node["id"], references)
        # Author the starter and first continuation; later blocks retain their own prompts.
        graph.connect(workspace, 1, 973, "prompt", "STRING")
        graph.connect(workspace, 1, 110, "prompt", "STRING")
        profile = "starter/first-extension prompt + shared references; later prompts/source canvas remain external"
        warnings += ["source-video branch can override generated width/height by design",
                     "starter and first extension share the active shot prompt; later blocks and audio-regeneration prompts remain community-owned",
                     "fixed extension blocks are not independent workspace shots"]
    elif case == "multiref-v2v":
        for target in (20, 131):
            graph.connect(workspace, 1, target, "prompt", "STRING")
            bind_native_images(graph, target, references)
        profile = "prompt + identity images only; source video, audio, masks, dimensions and duration remain external"
        warnings += ["source video determines latent shape and frame count; workspace size/duration are not connected",
                     "reference-video/audio routes remain external; workspace prompt validation cannot certify their semantics"]
    elif case == "continuum":
        graph.connect(workspace, 1, 312, "sequence_prompt", "STRING")
        graph.connect(workspace, 2, 312, "chunk_seconds", "FLOAT")
        for output, name in [(3, "width"), (4, "height")]:
            graph.connect(workspace, output, 312, name, "INT")
        for name in ("first_frame", "last_frame", "reference_video_1", "driving_audio", "audio_references"):
            graph.disconnect(312, name)
        for index in range(1, 10):
            graph.disconnect(348, f"reference_image_{index}")
        for index, reference in enumerate(references, 1):
            graph.connect(reference, 0, 348, f"reference_image_{index}", "IMAGE")
        # Widget ordering verified against the pinned V3.9 example and inheritance schema.
        values = graph.nodes[312]["widgets_values"]
        values[0], values[1] = "Fixed", 1
        values[16], values[19], values[22] = "Off", "shot-workspace-compat-independent-run", "Full Run"
        values[27], values[28], values[29] = "Manual", 704, 480
        graph.nodes[348]["widgets_values"][0] = "All chunks"
        profile = "reference-only, one chunk, fixed prompt, manual canvas, independent run"
        warnings += ["first/last images shift Picture numbering in hybrid mode; removed for this reference-only profile",
                     "multi-chunk per-shot prompts and resume/take mapping need a sequence/state adapter",
                     "only the prompt/media contract was checked; Continuum is not installed or executed"]
    manifest = json.loads((SOURCES / slug / "manifest.json").read_text(encoding="utf-8"))
    workflow.setdefault("extra", {})["shot_workspace_compatibility"] = {
        "source_repo": manifest["repo"], "source_commit": manifest["commit"], "source_workflow": filename,
        "source_sha256": hashlib.sha256((SOURCES / slug / "source" / filename).read_bytes()).hexdigest(),
        "license": manifest["license"], "verification": "JSON links / source contract only; no generation", "profile": profile,
        "warnings": warnings}
    before = preserved_continuity_nodes(original)
    after = preserved_continuity_nodes(workflow)
    return {"case": case, "slug": slug, "workflow": workflow, "original": original, "profile": profile,
            "warnings": warnings, "added_links": graph.added_links,
            "baseline_graph_issues": sorted(baseline), "new_graph_issues": sorted(set(graph.issues()) - baseline),
            "changed_continuity_nodes": [key for key, value in before.items() if after.get(key) != value]}


def build_local_motion_case():
    """Full core workflow plus the already installed Motion Context dependency."""
    result = build_case("official")
    workflow = result["workflow"]
    graph = Graph(workflow)
    workspace = next(n["id"] for n in workflow["nodes"] if n["type"] == "ShotWorkspace")
    native = next(n["id"] for n in workflow["nodes"] if n["type"] == "MiniMaxH3ReferenceToVideo")
    video = next(n["id"] for n in workflow["nodes"] if n["type"] == "CreateVideo")

    def add(kind, inputs, outputs, values, pos):
        return graph.add({"type": kind, "pos": pos, "size": [300, 200], "order": 0, "mode": 0, "flags": {},
            "inputs": [{"name": name, "type": port, "link": None} for name, port in inputs],
            "outputs": [{"name": name, "type": port, "links": []} for name, port in outputs],
            "properties": {"Node name for S&R": kind}, "widgets_values": values})

    context = add("MiniMaxH3MotionContext", [("conditioning", "CONDITIONING"), ("vae", "VAE"), ("latent", "LATENT"),
                  ("context_frames", "IMAGE"), ("context_latent", "LATENT"), ("audio_vae", "VAE"), ("context_audio", "AUDIO")],
                  [("conditioning", "CONDITIONING"), ("trim_frames", "INT")], ["22", 24], [1800, 1900])
    load = add("MiniMaxH3MotionContextLoadLatent", [], [("LATENT", "LATENT")], ["shot_workspace_compat", 0], [1450, 1900])
    trim = add("MiniMaxH3MotionContextTrim", [("images", "IMAGE"), ("audio", "AUDIO")],
               [("images", "IMAGE"), ("audio", "AUDIO")], [0, 24.0, True], [2200, 1900])
    save = add("MiniMaxH3MotionContextSaveLatent", [("latent", "LATENT")], [("latent_path", "STRING")],
               ["shot_workspace_compat/clip", 1], [2200, 2200])
    graph.replace_fanout(native, 0, context, 0)
    graph.connect(native, 0, context, "conditioning", "CONDITIONING")
    graph.connect(native, 1, context, "latent", "LATENT")
    graph.connect(load, 0, context, "context_latent", "LATENT")
    for name in ("vae", "audio_vae"):
        edge = next(l for l in workflow["links"] if l[0] == graph.input(native, name)["link"])
        graph.connect(edge[1], edge[2], context, name, "VAE")
    for name, kind, output in [("images", "IMAGE", 0), ("audio", "AUDIO", 1)]:
        edge = next(l for l in workflow["links"] if l[0] == graph.input(video, name)["link"])
        graph.connect(edge[1], edge[2], trim, name, kind)
        graph.connect(trim, output, video, name, kind)
        if name == "images":
            decoder = graph.nodes[edge[1]]
            samples = next(l for l in workflow["links"] if l[0] == graph.input(decoder["id"], "samples")["link"])
            graph.connect(samples[1], samples[2], save, "latent", "LATENT")
    graph.connect(context, 1, trim, "trim_frames", "INT")
    graph.connect(workspace, 6, trim, "fps", "FLOAT")
    graph.connect(workspace, 6, video, "fps", "FLOAT")
    result.update(case="motion-context-local", slug="motion-context-local", profile="installed Motion Context; external latent save/load and synchronized trim",
        warnings=["first run: Load clip_index=0, Save clip_index=1; next run: choose the prior clip explicitly",
                  "length is pre-trim; context frames reduce delivered duration",
                  "no automatic shot/job/revision registration; do not use one slot for unrelated shots"],
        added_links=result["added_links"] + graph.added_links, new_graph_issues=graph.issues(), changed_continuity_nodes=[])
    workflow["extra"]["shot_workspace_compatibility"].update(profile=result["profile"], warnings=result["warnings"],
        additional_dependency="already installed ComfyUI-H3-Motion-Context; installed code exercised with synthetic tensors")
    return result


def main():
    destination = ROOT / "examples" / "compatibility"
    destination.mkdir(parents=True, exist_ok=True)
    summary = []
    for case in list(CASES) + ["motion-context-local"]:
        result = build_local_motion_case() if case == "motion-context-local" else build_case(case)
        path = destination / f"{case}.json"
        path.write_text(json.dumps(result["workflow"], indent=2, ensure_ascii=False), encoding="utf-8")
        summary.append({k: v for k, v in result.items() if k not in {"workflow", "original"}})
    (destination / "validation.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps([{k: v for k, v in r.items() if k != "added_links"} for r in summary], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
