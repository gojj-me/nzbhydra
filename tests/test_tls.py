"""Real local HTTPS trust/hostname regressions; synthetic ephemeral keys only."""
from __future__ import print_function
import os,sys,tempfile,shutil,subprocess,threading,ssl,socket,unittest
from BaseHTTPServer import HTTPServer,BaseHTTPRequestHandler
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0]=[ROOT,ROOT+'/libs']
from bunch import Bunch
from requests.exceptions import SSLError
from nzbhydra import config,webaccess


class VerifiedHttpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.mkdtemp(prefix='hydra-synthetic-tls-')
        def run(args):
            with open(os.devnull,'wb') as output:
                subprocess.check_call(['openssl']+args,cwd=cls.folder,stdout=output,stderr=output)
        try:
            run(['req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                 '-subj','/CN=Synthetic Test CA','-keyout','ca.key','-out','ca.pem'])
            run(['req','-newkey','rsa:2048','-nodes','-subj','/CN=Synthetic HTTPS',
                 '-keyout','server.key','-out','server.csr'])
            with open(cls.folder+'/extensions','w') as output:
                output.write('subjectAltName=IP:127.0.0.1\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n')
            run(['x509','-req','-in','server.csr','-CA','ca.pem','-CAkey','ca.key',
                 '-CAcreateserial','-days','1','-extfile','extensions','-out','server.pem'])
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200);self.end_headers();self.wfile.write(b'synthetic response')
                def log_message(self,*args):pass
            class SyntheticServer(HTTPServer):
                def handle_error(self,request,address):
                    # Rejected client handshakes can reset a synthetic connection.
                    if not isinstance(sys.exc_info()[1],(socket.error,ssl.SSLError)):
                        HTTPServer.handle_error(self,request,address)
            cls.server=SyntheticServer(('127.0.0.1',0),Handler)
            cls.server.socket=ssl.wrap_socket(cls.server.socket,server_side=True,
                certfile=cls.folder+'/server.pem',keyfile=cls.folder+'/server.key')
            cls.thread=threading.Thread(target=cls.server.serve_forever);cls.thread.daemon=True;cls.thread.start()
            cls.port=cls.server.server_address[1]
        except:
            shutil.rmtree(cls.folder);raise

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(3)
        shutil.rmtree(cls.folder)

    def setUp(self):
        config.settings=Bunch.fromDict(config.initialConfig)
        webaccess.proxies=None

    def get(self,hostname='127.0.0.1'):
        return webaccess.get('https://%s:%d/'%(hostname,self.port),timeout=2)

    def test_untrusted_certificate_is_rejected_with_normal_verification(self):
        self.assertTrue(config.settings.main.verifySsl)
        with self.assertRaises(SSLError):self.get()
        self.assertTrue(config.settings.main.verifySsl)

    def test_valid_chain_to_explicit_test_ca_succeeds(self):
        # This CA exists only in the disposable test directory, not production.
        config.settings.main.verifySsl=self.folder+'/ca.pem'
        response=self.get()
        self.assertEqual(200,response.status_code)
        self.assertEqual(b'synthetic response',response.content)

    def test_trusted_chain_does_not_bypass_hostname_validation(self):
        config.settings.main.verifySsl=self.folder+'/ca.pem'
        with self.assertRaises(SSLError):self.get('localhost')


if __name__=='__main__':unittest.main(verbosity=2)
