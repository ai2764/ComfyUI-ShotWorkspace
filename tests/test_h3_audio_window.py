import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from h3_audio_window import audio_window_indices
from h3_audio_window import mask_h3_audio

class AudioWindowTests(unittest.TestCase):
    def test_only_audio_steps_wholly_inside_retained_speech_window_are_free(self):
        start,end=audio_window_indices(405,10.125,1.917,9.325)
        self.assertEqual((start,end),(77,373))
        self.assertGreaterEqual(start/40,1.917);self.assertLessEqual(end/40,9.325)
    def test_invalid_or_empty_windows_are_rejected(self):
        for args in [(405,10.125,9,1),(405,10.125,0,11),(405,10.125,1.001,1.002),(True,10,1,9)]:
            with self.subTest(args=args),self.assertRaises(ValueError):audio_window_indices(*args)

class NativeMaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import torch
            from comfy.nested_tensor import NestedTensor
        except ImportError:raise unittest.SkipTest('Run this class in the ComfyUI Torch environment.')
        cls.torch=torch;cls.NestedTensor=NestedTensor
    def latent(self):
        t=self.torch
        return {'samples':self.NestedTensor((t.ones((1,24,2,2,2)),t.full((1,32,2,405),2.0)))}
    def test_mask_fixes_only_prefix_tail_preserves_video_and_input(self):
        t=self.torch;original=self.latent();audio=original['samples'].unbind()[1]
        class VAE:
            audio_sample_rate=32000
            def encode(self,wave):
                assert wave.shape==(1,324000,2)
                return t.zeros_like(audio)
        result=mask_h3_audio(original,VAE(),{'sampling_end_s':10.125,'speech_start_s':1.917,'speech_end_s':9.325})
        video,masked=result['samples'].unbind();vm,am=result['noise_mask'].unbind()
        self.assertTrue(t.all(video==1));self.assertTrue(t.all(vm==1));self.assertTrue(t.all(audio==2))
        self.assertTrue(t.all(masked[...,:77]==0));self.assertTrue(t.all(masked[...,77:373]==2));self.assertTrue(t.all(masked[...,373:]==0))
        self.assertTrue(t.all(am[...,:77]==0));self.assertTrue(t.all(am[...,77:373]==1));self.assertTrue(t.all(am[...,373:]==0))
    def test_existing_mask_and_generic_latent_are_not_silently_replaced(self):
        for latent in [{'samples':self.torch.zeros(1)},{**self.latent(),'noise_mask':'existing'}]:
            with self.subTest(),self.assertRaises(ValueError):mask_h3_audio(latent,None,{})
    def test_latent_duration_mismatch_is_rejected_before_encoding(self):
        t=self.torch;latent={'samples':self.NestedTensor((t.ones((1,24,2,2,2)),t.zeros((1,32,2,200))))}
        with self.assertRaisesRegex(ValueError,'timeline'):
            mask_h3_audio(latent,None,{'sampling_end_s':10.125,'speech_start_s':1.917,'speech_end_s':9.325})

if __name__=='__main__':unittest.main()
