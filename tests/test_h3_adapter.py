import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from h3_adapter import with_h3_delivery_timing
from contract import make_shot
from test_authoring_regressions import data,sections,CandidateClient
from llm_runtime import AuthoringService

class AdapterTests(unittest.TestCase):
    def graph(self):return {'source':{'class_type':'GetVideoComponents','inputs':{}},'mc':{'class_type':'MiniMaxH3MotionContext','inputs':{'context_length':'22','context_frames':['source',0]}},'trim':{'class_type':'MiniMaxH3MotionContextTrim','inputs':{'trim_frames':['mc',1],'fps':['source',2]}}}
    def test_timing_declaration_invalidates_old_prompt_without_mutating_workspace(self):
        ws=data();result=AuthoringService(CandidateClient(sections())).write_prompt(ws)
        ws['shots'][0].update(prompt_sections=result['prompt_sections'],prompt_basis=result['prompt_basis'])
        original=copy.deepcopy(ws);self.assertTrue(make_shot(json.dumps(ws))['prompt_ready'])
        changed=with_h3_delivery_timing(ws,self.graph(),'video',source_frames=51,source_fps=24)
        self.assertEqual(ws,original);self.assertTrue(make_shot(json.dumps(changed))['prompt_stale'])
        self.assertEqual(changed['shots'][0]['continuity']['delivery_timing']['prefix_trim_frames'],22)
    def test_wrong_trim_wiring_or_unverified_source_is_rejected(self):
        for frames,fps in [(21,24),(51,30),(True,24)]:
            with self.subTest(frames=frames,fps=fps),self.assertRaises(ValueError):
                with_h3_delivery_timing(data(),self.graph(),'video',source_frames=frames,source_fps=fps)
        graph=self.graph();graph['trim']['inputs']['trim_frames']=22
        with self.assertRaisesRegex(ValueError,'linked'):with_h3_delivery_timing(data(),graph,'video',source_frames=51,source_fps=24)
    def test_missing_or_wrong_kind_context_and_wrong_trim_fps_are_rejected(self):
        graph=self.graph();del graph['mc']['inputs']['context_frames']
        with self.assertRaisesRegex(ValueError,'active'):with_h3_delivery_timing(data(),graph,'video',source_frames=51,source_fps=24)
        with self.assertRaisesRegex(ValueError,'active'):with_h3_delivery_timing(data(),self.graph(),'latent',source_frames=51,source_fps=24)
        graph=self.graph();graph['trim']['inputs']['fps']=30
        with self.assertRaisesRegex(ValueError,'fps'):with_h3_delivery_timing(data(),graph,'video',source_frames=51,source_fps=24)
        graph=self.graph();graph['other']={'class_type':'GetVideoComponents','inputs':{}};graph['trim']['inputs']['fps']=['other',2]
        with self.assertRaisesRegex(ValueError,'fps'):with_h3_delivery_timing(data(),graph,'video',source_frames=51,source_fps=24)

if __name__=='__main__':unittest.main()
