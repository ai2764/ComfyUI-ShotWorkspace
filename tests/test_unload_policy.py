import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import generation


class UnloadPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                cls.calls.append(self.path)
                self.send_response(503 if self.path=='/fail' else 200)
                self.end_headers()
            def log_message(self,*args):pass
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.origin=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def setUp(self):self.calls.clear()

    def release(self,config):
        fn=getattr(generation,'release_model',None)
        self.assertTrue(callable(fn),'Explicit generation unload policy is not implemented')
        fn(config)

    def config(self,**kwargs):
        return dict(base_url=self.origin+'/v1',unload_url=self.origin+'/unload',**kwargs)

    def test_existing_config_without_opt_in_does_not_unload(self):
        self.release(self.config());self.assertEqual(self.calls,[])

    def test_unchecked_does_not_unload_even_for_local_server(self):
        self.release(self.config(unload_before_generation=False));self.assertEqual(self.calls,[])

    def test_checked_posts_unload_before_returning(self):
        self.release(self.config(unload_before_generation=True));self.assertEqual(self.calls,['/unload'])

    def test_checked_without_endpoint_is_explicit_error(self):
        with self.assertRaisesRegex(ValueError,'unload URL'):
            self.release({'unload_before_generation':True})

    def test_failed_unload_is_not_treated_as_success(self):
        config=self.config(unload_before_generation=True);config['unload_url']=self.origin+'/fail'
        with self.assertRaises(urllib.error.HTTPError):self.release(config)

    def test_unchecked_remote_url_does_not_trigger_detection_or_network(self):
        self.release({'base_url':'https://remote.invalid/v1','unload_url':'https://remote.invalid/unload','unload_before_generation':False})
        self.assertEqual(self.calls,[])

    def test_checked_preserves_same_origin_validation(self):
        config=self.config(unload_before_generation=True);config['unload_url']='https://other.invalid/unload'
        with self.assertRaisesRegex(ValueError,'same origin'):self.release(config)

    def test_invalid_boolean_cannot_silently_enable_unload(self):
        with self.assertRaisesRegex(ValueError,'boolean'):self.release(self.config(unload_before_generation='false'))


if __name__=='__main__':unittest.main()
