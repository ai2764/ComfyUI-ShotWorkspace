import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from contract import make_shot
from workflow_compat import Graph
from install_example_inputs import install


class PublicExamplesTests(unittest.TestCase):
    def test_all_three_examples_have_valid_links_and_current_prompts(self):
        files = sorted((ROOT / "examples/verified").glob("[0-9]*.json"))
        self.assertEqual(len(files), 3)
        for file in files:
            with self.subTest(file=file.name):
                graph = json.loads(file.read_text(encoding="utf-8"))
                self.assertEqual(Graph(graph).issues(), [])
                node = next(n for n in graph["nodes"] if n["type"] == "ShotWorkspace")
                workspace = json.loads(node["widgets_values"][0])
                self.assertNotIn("llm_config", workspace)
                self.assertTrue(make_shot(json.dumps(workspace))["prompt_ready"])
                for asset in workspace["assets"]:
                    self.assertTrue((ROOT / "examples/inputs" / asset["image"]).is_file())
                self.assertTrue(all("widgets_values_named" not in n for n in graph["nodes"]))

    def test_multiref_keeps_original_canvas_and_places_interface_outside_controller_groups(self):
        old = json.loads((ROOT / "examples/upstream/multiref/NEW - AV Extension.json").read_text(encoding="utf-8"))
        new = json.loads((ROOT / "examples/verified/02-multiref-latent-context.json").read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in new["nodes"]}
        self.assertEqual(len(old["nodes"]), 102)
        self.assertEqual(len(new["nodes"]), 108)
        self.assertEqual(new["groups"], old["groups"])
        for original in old["nodes"]:
            node = nodes[original["id"]]
            self.assertEqual(node["pos"], original["pos"])
            self.assertEqual(node.get("size"), original.get("size"))
        interface = nodes[2001]
        self.assertEqual(interface["mode"], 0)
        x, y = interface["pos"]
        for group in new["groups"]:
            gx, gy, width, height = group["bounding"]
            self.assertFalse(gx <= x <= gx + width and gy <= y <= gy + height)

    def test_upstream_snapshots_are_exact_and_licenses_exist(self):
        expected = {
            "motion-context/H3-Motion-Context-v0.7.json": "0c33daa8da99001f6b716f251667ad01e4b3471351081426f7535478d3ee2800",
            "multiref/NEW - AV Extension.json": "87a85563ab868d4202a3f37f02e30d4749b865bcf8b050f55991a6c980ca9fa4",
        }
        for name, digest in expected.items():
            path = ROOT / "examples/upstream" / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            self.assertTrue((path.parent / "LICENSE").is_file())

    def test_reference_layout_is_separate_from_generation_examples(self):
        graph = json.loads((ROOT / "examples/reference/motion-context-original-connected.json").read_text(encoding="utf-8"))
        self.assertEqual(Graph(graph).issues(), [])

    def test_first_latent_clip_bypasses_empty_adapter_and_continuation_uses_next_slot(self):
        bootstrap = json.loads((ROOT / "examples/helpers/native-latent-bootstrap.json").read_text(encoding="utf-8"))
        continuation = json.loads((ROOT / "examples/verified/03-motion-context-native-latent.json").read_text(encoding="utf-8"))
        first, second = Graph(bootstrap), Graph(continuation)
        self.assertEqual(first.issues(), [])
        link_id = first.input(12, "context_latent")["link"]
        edge = next(link for link in bootstrap["links"] if link[0] == link_id)
        self.assertEqual(edge[1], 11)
        self.assertEqual(first.nodes[11]["widgets_values"][1], 0)
        self.assertEqual(first.nodes[23]["widgets_values"][1], 1)
        self.assertEqual(second.nodes[11]["widgets_values"][1], 1)
        self.assertEqual(second.nodes[23]["widgets_values"][1], 2)


class FixtureInstallerTests(unittest.TestCase):
    def test_install_is_complete_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            first = install(temp)
            self.assertEqual(len(first), 5)
            self.assertEqual(first, install(temp))
            self.assertEqual(set(first), {p.name for p in Path(temp).iterdir()})

    def test_conflict_does_not_overwrite_or_partially_install(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "shot-workspace-example-previous.mp4"
            target.write_bytes(b"existing user video")
            with self.assertRaises(FileExistsError):
                install(temp)
            self.assertEqual(target.read_bytes(), b"existing user video")
            self.assertEqual(list(Path(temp).iterdir()), [target])
