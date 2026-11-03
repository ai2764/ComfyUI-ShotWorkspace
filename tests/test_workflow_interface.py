import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from integrate_motion_context import SOURCE, SOURCE_SHA256, integrate, audit


class PreservationTests(unittest.TestCase):
    def test_original_canvas_and_all_internal_processing_are_preserved(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), SOURCE_SHA256)
        source = json.loads(SOURCE.read_text(encoding='utf-8'))
        saved = copy.deepcopy(source)
        result = integrate(source, {'version': 1, 'assets': [], 'shots': []})
        report = audit(source, result)
        self.assertEqual(source, saved)
        self.assertEqual(report['changed_node_definitions'], [])
        self.assertTrue(report['original_groups_unchanged'])
        self.assertTrue(report['subgraphs_unchanged'])
        self.assertEqual(set(report['removed_input_links']), {975, 1092})
        self.assertEqual(report['changed_retained_links'], [])
        self.assertEqual(report['new_graph_issues'], [])

    def test_audit_rejects_moving_or_reconfiguring_an_original_node(self):
        source = json.loads(SOURCE.read_text(encoding='utf-8'))
        result = integrate(source, {'version': 1, 'assets': [], 'shots': []})
        result['nodes'][0]['pos'][0] += 1
        self.assertEqual(audit(source, result)['changed_node_definitions'], [source['nodes'][0]['id']])


if __name__ == '__main__': unittest.main()
