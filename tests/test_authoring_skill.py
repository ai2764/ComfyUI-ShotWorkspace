import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from authoring_skill import load_rule_bundle,STAGE_FILES

class RuleBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for name in {name for files in STAGE_FILES.values() for name in files}:
            file=self.root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('Rule from '+name,encoding='utf-8')
    def test_stage_scope_cache_and_manifest_copies(self):
        first=load_rule_bundle('prompt_write',self.root)
        self.assertIn('SKILL.md',first.text);self.assertNotIn('analyse.md',first.text)
        self.assertEqual(len(first.version),64)
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Cache reread content')):
            self.assertIs(load_rule_bundle('prompt_write',self.root),first)
        manifest=first.manifest();manifest['files'].clear()
        self.assertTrue(first.manifest()['files'])
    def test_edit_invalidates_cache_but_old_snapshot_stays_stable(self):
        old=load_rule_bundle('prompt_write',self.root)
        target=self.root/STAGE_FILES['prompt_write'][-1];target.write_text('Changed complete writing rule',encoding='utf-8')
        new=load_rule_bundle('prompt_write',self.root)
        self.assertNotEqual(old.version,new.version);self.assertNotIn('Changed complete',old.text);self.assertIn('Changed complete',new.text)
    def test_missing_empty_unknown_fail_closed(self):
        with self.assertRaises(ValueError):load_rule_bundle('../private',self.root)
        target=self.root/STAGE_FILES['asset_analysis'][-1];target.write_text('   ',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'empty'):load_rule_bundle('asset_analysis',self.root)
        target.unlink()
        with self.assertRaisesRegex(ValueError,'Missing'):load_rule_bundle('asset_analysis',self.root)

if __name__=='__main__':unittest.main()
