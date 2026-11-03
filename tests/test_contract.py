import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contract import make_shot, input_signature, compose_prompt, llm_request, SECTION_KEYS


def workspace():
    return {"version": 1, "assets": [
        {"id": "actor", "name": "Person", "image": "actor.png", "description": "A person wearing a blue coat"},
        {"id": "scene", "name": "Room", "image": "room.png", "description": "A small room"}],
        "shots": [{"id": "s1", "title": "Arrival", "brief": "Walk into the room", "duration_s": 5,
                   "width": 704, "height": 480, "refs": [
                       {"asset_id": "scene", "role": "scene", "notes": "Use the room geography"},
                       {"asset_id": "actor", "role": "identity", "notes": "Identity only"}]}],
        "active_shot_id": "s1"}


class ContractTests(unittest.TestCase):
    def test_selected_references_keep_order_and_freeze_descriptions(self):
        data = workspace()
        shot = make_shot(json.dumps(data))
        data["assets"][1]["description"] = "Changed"
        self.assertEqual([r["asset_id"] for r in shot["references"]], ["scene", "actor"])
        self.assertEqual([r["picture_index"] for r in shot["references"]], [1, 2])
        self.assertEqual(shot["references"][0]["description"], "A small room")

    def test_h3_frames_are_rounded_up_without_changing_requested_duration(self):
        shot = make_shot(json.dumps(workspace()))
        self.assertEqual(shot["duration_s"], 5)
        self.assertEqual(shot["length"], 124)
        self.assertEqual(shot["fps"], 24)

    def test_manual_prompt_has_six_sections_and_exact_picture_bindings(self):
        data = workspace()
        data["shots"][0]["prompt_sections"] = {key: "None" for key in SECTION_KEYS}
        data["shots"][0]["prompt_sections"]["subject_definitions"] = "Room <Picture 1>, person <Picture 2>"
        data["shots"][0]["prompt_basis"] = make_shot(json.dumps(data))["inputs"]
        shot = make_shot(json.dumps(data))
        self.assertTrue(shot["prompt_ready"])
        self.assertTrue(compose_prompt(shot).startswith("subject_definitions:\n"))
        data["shots"][0]["prompt_sections"]["summary"] = "Unexpected <Picture 3>"
        with self.assertRaisesRegex(ValueError, "unselected"):
            make_shot(json.dumps(data))

    def test_draft_is_allowed_but_not_marked_generation_ready(self):
        shot = make_shot(json.dumps(workspace()))
        self.assertFalse(shot["prompt_ready"])
        self.assertEqual(compose_prompt(shot), "")

    def test_signature_changes_for_duration_notes_and_description_not_unselected_assets(self):
        data = workspace()
        original = input_signature(make_shot(json.dumps(data)))
        for path, value in [("duration_s", 6), ("brief", "Stop")]:
            revised = copy.deepcopy(data)
            revised["shots"][0][path] = value
            self.assertNotEqual(original, input_signature(make_shot(json.dumps(revised))))
        data["assets"].append({"id": "unused", "image": "other.png", "description": "Other"})
        self.assertEqual(original, input_signature(make_shot(json.dumps(data))))

    def test_missing_assets_duplicates_invalid_size_and_unknown_version_fail_clearly(self):
        for change, reason in [
            (lambda d: d["shots"][0]["refs"].append(d["shots"][0]["refs"][0]), "Duplicate"),
            (lambda d: d["assets"].pop(), "missing"),
            (lambda d: d["shots"][0].update(width=705), "multiple of 32"),
            (lambda d: d.update(version=2), "version")]:
            data = workspace()
            change(data)
            with self.assertRaisesRegex(ValueError, reason):
                make_shot(json.dumps(data))

    def test_llm_request_is_text_only_scoped_to_selected_shot_and_has_no_secret(self):
        config = {"base_url": "http://localhost:1234/v1", "text_model": "text-model", "vision_model": "vision-model",
                  "api_key_env": "LOCAL_LLM_KEY", "timeout_s": 120}
        request = llm_request(make_shot(json.dumps(workspace())), config, "write_prompt")
        self.assertEqual(request["url"], "http://localhost:1234/v1/chat/completions")
        self.assertEqual(request["body"]["model"], "text-model")
        self.assertNotIn("Authorization", request)
        self.assertNotIn("image_url", json.dumps(request))
        payload = json.loads(request["body"]["messages"][1]["content"])
        self.assertEqual(len(payload["references"]), 2)
        self.assertNotIn("assets", payload)

    def test_accepted_prompt_becomes_stale_on_reference_description_or_duration_change(self):
        data = workspace()
        source = data["shots"][0]
        source["prompt_sections"] = {key: "None" for key in SECTION_KEYS}
        source["prompt_sections"]["subject_definitions"] = "<Picture 1> room, <Picture 2> identity"
        source["prompt_basis"] = make_shot(json.dumps(data))["inputs"]
        self.assertTrue(make_shot(json.dumps(data))["prompt_ready"])
        for change in [lambda d: d["shots"][0].update(duration_s=6),
                       lambda d: d["assets"][0].update(description="A red coat"),
                       lambda d: d["shots"][0]["refs"].pop()]:
            revised = copy.deepcopy(data)
            change(revised)
            shot = make_shot(json.dumps(revised))
            self.assertTrue(shot["prompt_stale"])
            self.assertFalse(shot["prompt_ready"])
            with self.assertRaisesRegex(ValueError, "stale"):
                compose_prompt(shot)

    def test_unaccepted_prompt_editor_changes_block_old_prompt(self):
        data = workspace()
        data["shots"][0]["prompt_sections"] = {key: "None" for key in SECTION_KEYS}
        data["shots"][0]["prompt_sections"]["subject_definitions"] = "<Picture 1> <Picture 2>"
        data["shots"][0]["prompt_editor_dirty"] = True
        self.assertFalse(make_shot(json.dumps(data))["prompt_ready"])

    def test_imported_prompt_without_basis_requires_acceptance_even_after_editing(self):
        data = workspace()
        data["shots"][0]["prompt_sections"] = {key: "None" for key in SECTION_KEYS}
        data["shots"][0]["prompt_sections"]["subject_definitions"] = "<Picture 1> <Picture 2>"
        for brief in ["Walk", "Run"]:
            data["shots"][0]["brief"] = brief
            shot = make_shot(json.dumps(data))
            self.assertFalse(shot["prompt_ready"])
            self.assertTrue(shot["prompt_stale"])

    def test_description_request_defines_a_json_response(self):
        config = {"base_url": "http://localhost:1234/v1", "text_model": "text-model"}
        request = llm_request(make_shot(json.dumps(workspace())), config, "refine_description")
        self.assertEqual(request["body"]["response_format"], {"type": "json_object"})
        system = request["body"]["messages"][0]["content"]
        self.assertIn("JSON", system)
        self.assertIn('"description"', system)


if __name__ == "__main__":
    unittest.main()
