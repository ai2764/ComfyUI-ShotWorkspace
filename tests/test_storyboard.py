import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storyboard import make_storyboard, require_applied_storyboard


class StoryboardTests(unittest.TestCase):
    def state(self):
        return {'version': 1, 'assets': [], 'shots': [{'id': 's1', 'title': 'Arrival', 'refs': []}], 'active_shot_id': 's1'}

    def test_bundle_is_stable_and_copies_source(self):
        source = self.state()
        packet = make_storyboard(json.dumps(source))
        source['shots'][0]['title'] = 'Changed'
        self.assertEqual(packet['workspace']['shots'][0]['title'], 'Arrival')
        self.assertEqual(packet['revision'], make_storyboard(json.dumps(self.state()))['revision'])

    def test_optional_link_requires_explicit_application_and_rejects_updates(self):
        state = self.state()
        packet = make_storyboard(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'Apply storyboard'):
            require_applied_storyboard(state, packet)
        state['storyboard_source_revision'] = packet['revision']
        require_applied_storyboard(state, packet)
        updated = self.state(); updated['shots'][0]['title'] = 'New title'
        with self.assertRaisesRegex(ValueError, 'Apply storyboard'):
            require_applied_storyboard(state, make_storyboard(json.dumps(updated)))
        require_applied_storyboard(state, None)

    def test_no_shots_cannot_be_executed_and_tampered_packet_is_rejected(self):
        empty = self.state(); empty['shots'] = []
        with self.assertRaisesRegex(ValueError, 'Plan'):
            make_storyboard(json.dumps(empty))
        packet = make_storyboard(json.dumps(self.state()))
        packet['workspace']['shots'][0]['title'] = 'Tampered'
        with self.assertRaises(ValueError):
            require_applied_storyboard({}, packet)
