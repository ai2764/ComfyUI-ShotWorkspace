import ast,unittest
from pathlib import Path
class DefaultsTests(unittest.TestCase):
    def test_config_node_defaults_do_not_depend_on_the_development_server(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'nodes.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ShotWorkspaceLLMConfig')
        env={};exec(compile(ast.Module(body=[cls],type_ignores=[]),'node_schema','exec'),env)
        fields=env['ShotWorkspaceLLMConfig'].INPUT_TYPES()['required']
        self.assertEqual(fields['base_url'][1]['default'],'http://127.0.0.1:1234/v1')
        self.assertEqual(fields['text_model'][1]['default'],'')
        self.assertEqual(fields['vision_model'][1]['default'],'')
