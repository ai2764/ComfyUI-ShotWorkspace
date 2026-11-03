import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from workflow_compat import Graph, build_case, build_local_motion_case, CASES, preserved_continuity_nodes, port_compatible


class GraphTests(unittest.TestCase):
    def test_reconnect_removes_old_backlinks_and_creates_typed_edge(self):
        data = {"nodes": [
            {"id": 1, "type": "Old", "outputs": [{"type": "STRING", "links": [1]}]},
            {"id": 2, "type": "Target", "inputs": [{"name": "prompt", "type": "STRING", "link": 1}]},
            {"id": 3, "type": "Workspace", "outputs": [{"type": "STRING", "links": []}]}],
            "links": [[1, 1, 0, 2, 0, "STRING"]], "last_link_id": 1}
        graph = Graph(data)
        graph.connect(3, 0, 2, "prompt", "STRING")
        self.assertEqual(graph.nodes[1]["outputs"][0]["links"], [])
        self.assertEqual(len(data["links"]), 1)
        self.assertEqual(data["links"][0][1], 3)
        self.assertEqual(graph.issues(), [])

    def test_custom_packets_are_not_interchangeable_even_if_both_are_dicts(self):
        for target in ["MINIMAX_H3_TIMELINE_PLAN", "NG_DIRECTOR_RESULT", "H3_CONTINUUM_REFERENCE_IMAGES_V39"]:
            self.assertFalse(port_compatible("SHOT", target))
        self.assertTrue(port_compatible("IMAGE", "IMAGE"))
        self.assertTrue(port_compatible("FLOAT", "FLOAT,INT,BOOLEAN"))
        self.assertFalse(port_compatible("FLOAT", "INT"))


class CommunityWorkflowTests(unittest.TestCase):
    def test_patched_workflows_keep_continuity_and_new_edges_are_valid(self):
        for case in CASES:
            with self.subTest(case=case):
                result = build_case(case)
                self.assertEqual(result["new_graph_issues"], [])
                self.assertEqual(result["changed_continuity_nodes"], [])
                self.assertGreater(len(result["added_links"]), 0)
                self.assertEqual(preserved_continuity_nodes(result["original"]),
                                 preserved_continuity_nodes(result["workflow"]))

    def test_motion_context_path_still_uses_previous_latent_and_trim_output(self):
        result = build_case("motion-context")
        nodes = {n["id"]: n for n in result["workflow"]["nodes"]}
        self.assertTrue(next(i for i in nodes[495]["inputs"] if i["name"] == "context_latent")["link"])
        self.assertTrue(next(i for i in nodes[499]["inputs"] if i["name"] == "trim_frames")["link"])

    def test_multiref_does_not_override_source_canvas_or_noise_masks(self):
        result = build_case("multiref-av")
        old = Graph(copy.deepcopy(result["original"]))
        new = Graph(copy.deepcopy(result["workflow"]))
        for name in ("source_width", "source_height", "start_mode"):
            self.assertEqual(old.input(972, name), new.input(972, name))
        self.assertEqual(old.nodes[103], new.nodes[103])
        for target in (973, 110):
            edge = next(l for l in result["workflow"]["links"] if l[0] == new.input(target, "prompt")["link"])
            self.assertEqual(new.nodes[edge[1]]["type"], "ShotWorkspace")

    def test_v2v_keeps_source_video_audio_and_latent_shape_controls(self):
        result = build_case("multiref-v2v")
        before, after = Graph(result["original"]), Graph(result["workflow"])
        for node in (20, 131):
            for name in ("ref_videos.ref_video_0", "ref_video_audios.ref_video_audio_0"):
                self.assertEqual(before.input(node, name), after.input(node, name))
        self.assertEqual(before.nodes[130], after.nodes[130])

    def test_continuum_reference_only_profile_does_not_shift_picture_indices(self):
        result = build_case("continuum")
        graph = Graph(result["workflow"])
        self.assertIsNone(graph.input(312, "first_frame")["link"])
        self.assertIsNone(graph.input(312, "last_frame")["link"])
        for index in (1, 2):
            self.assertIsNotNone(graph.input(348, f"reference_image_{index}")["link"])
        for index in range(3, 10):
            self.assertIsNone(graph.input(348, f"reference_image_{index}")["link"])
        self.assertIn("reference-only", result["profile"])

    def test_local_motion_variant_contains_complete_external_latent_and_trim_route(self):
        result = build_local_motion_case()
        self.assertEqual(result["new_graph_issues"], [])
        types = {n["type"] for n in result["workflow"]["nodes"]}
        self.assertTrue({"MiniMaxH3MotionContext", "MiniMaxH3MotionContextTrim",
                         "MiniMaxH3MotionContextLoadLatent", "MiniMaxH3MotionContextSaveLatent"}.issubset(types))


if __name__ == "__main__":
    unittest.main()
