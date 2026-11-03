import unittest

from generation import continuation_status


class ContinuationMetadataTests(unittest.TestCase):
    def test_multiref_existing_video_context(self):
        graph = {'source': {'class_type': 'MiniMaxH3CropTo32'}, 'mask': {
            'class_type': 'MiniMaxH3StartMaskedContext',
            'inputs': {'source_frames': ['source', 0]}}}
        self.assertIn('External MultiRef', continuation_status(graph))

    def test_multiref_generated_starter_context(self):
        graph = {'starter': {'class_type': 'SamplerCustomAdvanced'}, 'mask': {
            'class_type': 'MiniMaxH3StartMaskedContext',
            'inputs': {'live_starter_latent': ['starter', 0]}}}
        self.assertIn('External MultiRef', continuation_status(graph))

    def test_multiref_later_extension_context(self):
        graph = {'previous': {'class_type': 'SamplerCustomAdvanced'}, 'mask': {
            'class_type': 'MiniMaxH3GeneratedAVMaskedContext',
            'inputs': {'source_latent': ['previous', 0]}}}
        self.assertIn('External MultiRef', continuation_status(graph))

    def test_fresh_target_latent_is_not_previous_context(self):
        graph = {'target': {'class_type': 'MiniMaxH3ReferenceToVideo'}, 'mask': {
            'class_type': 'MiniMaxH3GeneratedAVMaskedContext',
            'inputs': {'latent': ['target', 1]}}}
        self.assertTrue(continuation_status(graph).startswith('Standalone'))

    def test_dangling_context_is_not_reported_as_wired(self):
        graph = {'mask': {'class_type': 'MiniMaxH3StartMaskedContext',
                          'inputs': {'source_frames': ['missing', 0]}}}
        self.assertTrue(continuation_status(graph).startswith('Standalone'))

    def test_classic_motion_context_still_detected(self):
        graph = {'frames': {'class_type': 'LoadImage'}, 'context': {
            'class_type': 'MiniMaxH3MotionContext',
            'inputs': {'context_frames': ['frames', 0]}}}
        self.assertIn('External Motion Context', continuation_status(graph))

    def test_classic_zero_clip_remains_standalone(self):
        graph = {'cache': {'class_type': 'MiniMaxH3MotionContextLoadLatent',
                           'inputs': {'clip_index': 0}}, 'context': {
            'class_type': 'MiniMaxH3MotionContext',
            'inputs': {'context_latent': ['cache', 0]}}}
        self.assertTrue(continuation_status(graph).startswith('Standalone'))

    def test_malformed_context_link_does_not_raise(self):
        graph = {'context': {'class_type': 'MiniMaxH3MotionContext',
                             'inputs': {'context_frames': []}}}
        self.assertTrue(continuation_status(graph).startswith('Standalone'))


if __name__ == '__main__':
    unittest.main()
