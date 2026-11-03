import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generation import select_generation_branch


class GenerationTests(unittest.TestCase):
    def test_only_dependent_output_and_its_ancestors_are_submitted(self):
        graph={
            '1':{'class_type':'ShotWorkspace','inputs':{}},
            '2':{'class_type':'SharedLoader','inputs':{}},
            '3':{'class_type':'Sampler','inputs':{'prompt':['1',1],'model':['2',0]}},
            '4':{'class_type':'SaveVideo','inputs':{'video':['3',0]}},
            '5':{'class_type':'OtherSampler','inputs':{'model':['2',0]}},
            '6':{'class_type':'SaveVideo','inputs':{'video':['5',0]}}}
        selected,outputs=select_generation_branch(graph,'1',{'SaveVideo'})
        self.assertEqual(set(selected),{'1','2','3','4'})
        self.assertEqual(outputs,['4'])

    def test_rejects_unconnected_workbench_even_if_another_video_output_exists(self):
        graph={'1':{'class_type':'ShotWorkspace','inputs':{}},'2':{'class_type':'SaveVideo','inputs':{}}}
        with self.assertRaisesRegex(ValueError,'connected'):
            select_generation_branch(graph,'1',{'SaveVideo'})


if __name__=='__main__':unittest.main()
