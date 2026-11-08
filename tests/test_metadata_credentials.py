"""Synthetic TMDB credential, metadata, API and export controls; no providers."""
from __future__ import print_function,unicode_literals
import os,sys,tempfile,shutil,json,unittest,logging,io
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0]=[ROOT,ROOT+'/libs']
from bunch import Bunch
from requests import Response
from requests.exceptions import Timeout
from furl import furl
from nzbhydra import config,database,infos,webaccess,redaction
from nzbhydra.metadata_credentials import tmdb_api_key,MetadataCredentialUnavailable
import nzbhydra.metadata_credentials as credentials

KEY='invented-metadata-api-key'
IMAGE={'images':{'secure_base_url':'https://images.example.invalid/','poster_sizes':['w92']}}
MOVIE={'id':123,'title':'Synthetic Movie','release_date':'2020-01-01','poster_path':'/synthetic.jpg'}

class MetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.mkdtemp(prefix='hydra-metadata-test-')
        database.init_db(cls.folder+'/synthetic.db')
        global web
        from nzbhydra import web
        web.app.template_folder=ROOT+'/templates'
    @classmethod
    def tearDownClass(cls):
        database.db.stop();database.db.close();shutil.rmtree(cls.folder)
    def setUp(self):
        config.settings=Bunch.fromDict(config.initialConfig)
        self.original_env={key:os.environ.get(key) for key in ['NZBHYDRA_TMDB_API_KEY','NZBHYDRA_TMDB_API_KEY_FILE']}
        for key in self.original_env:os.environ.pop(key,None)
        self.default=credentials.DEFAULT_TMDB_KEY_FILE
        credentials.DEFAULT_TMDB_KEY_FILE=self.folder+'/missing'
        self.original_get=webaccess.get
        self.original_start=web.startSearch
        self.calls=[];self.status=200;self.payloads={}
        def get(url,**kwargs):
            self.calls.append((url,kwargs))
            path=str(furl(url).path)
            payload=self.payloads.get(path,{})
            r=Response();r.status_code=self.status;r.url=url
            r._content=json.dumps(payload).encode('utf8')
            return r
        webaccess.get=get
        web.flask_cache.clear()
        database.MovieIdCache.delete().execute()
    def tearDown(self):
        webaccess.get=self.original_get;web.startSearch=self.original_start
        credentials.DEFAULT_TMDB_KEY_FILE=self.default
        for key,value in self.original_env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    def key(self,value=KEY):os.environ['NZBHYDRA_TMDB_API_KEY']=value
    def key_file(self,body=KEY):
        path=self.folder+'/tmdb-api-key'
        with io.open(path,'w',encoding='utf8') as out:out.write(body)
        os.chmod(path,0o600)
        os.environ['NZBHYDRA_TMDB_API_KEY_FILE']=path
        return path
    def autocomplete(self):
        return web.app.test_client().get('/internalapi/autocomplete?type=movie&input=synthetic')
    def movie_payloads(self):
        self.payloads={'/3/configuration':IMAGE,'/3/search/movie':{'results':[MOVIE]},
                      '/3/movie/123':{'imdb_id':'tt0000123','title':'Synthetic Movie'},
                      '/3/find/tt0000123':{'movie_results':[MOVIE]}}

    def test_missing_and_empty_credentials_send_no_requests(self):
        for value in [None,'',' \n ']:
            if value is None:os.environ.pop('NZBHYDRA_TMDB_API_KEY',None)
            else:self.key(value)
            self.assertEqual((None,None),infos.tmdbid_to_imdbid('123'))
            self.assertEqual((None,None),infos.imdbid_to_tmdbid('0000123'))
            with self.assertRaises(infos.TmdbUnavailable):infos.find_movie_ids('synthetic')
        self.assertEqual([],self.calls)

    def test_default_file_and_explicit_file_rotation(self):
        path=self.key_file(KEY+'\n')
        self.assertEqual(KEY,tmdb_api_key())
        os.environ.pop('NZBHYDRA_TMDB_API_KEY_FILE')
        credentials.DEFAULT_TMDB_KEY_FILE=path
        self.assertEqual(KEY,tmdb_api_key())
        with io.open(path,'w',encoding='utf8') as out:out.write('invented-rotated-key')
        self.assertEqual('invented-rotated-key',tmdb_api_key())

    def test_file_size_boundary_never_accepts_a_truncated_prefix(self):
        self.key_file('x'*4096+'\r\n')
        self.assertEqual(4096,len(tmdb_api_key()))
        self.key_file('x'*4096+'\n'+'trailing-data'*100)
        with self.assertRaises(MetadataCredentialUnavailable):tmdb_api_key()

    def test_environment_precedence_and_explicit_empty_override(self):
        self.key_file();self.key('invented-env-key')
        self.assertEqual('invented-env-key',tmdb_api_key())
        self.key('')
        with self.assertRaises(MetadataCredentialUnavailable):tmdb_api_key()
        os.environ.pop('NZBHYDRA_TMDB_API_KEY')
        os.environ['NZBHYDRA_TMDB_API_KEY_FILE']=''
        with self.assertRaises(MetadataCredentialUnavailable):tmdb_api_key()

    def test_invalid_oversized_unreadable_and_nonregular_files(self):
        for value in ['x'*4097,'embedded\nnewline','\u00e5']:
            self.key_file(value)
            with self.assertRaises(MetadataCredentialUnavailable):tmdb_api_key()
        os.environ['NZBHYDRA_TMDB_API_KEY_FILE']=self.folder+'/absent'
        with self.assertRaises(MetadataCredentialUnavailable):tmdb_api_key()
        os.environ['NZBHYDRA_TMDB_API_KEY_FILE']=self.folder
        with self.assertRaises(MetadataCredentialUnavailable):tmdb_api_key()
        fifo=self.folder+'/fifo';os.mkfifo(fifo)
        os.environ['NZBHYDRA_TMDB_API_KEY_FILE']=fifo
        try:
            with self.assertRaises(MetadataCredentialUnavailable):tmdb_api_key()
        finally:os.unlink(fifo)

    def test_configured_search_and_conversion_request_contracts(self):
        self.key();self.movie_payloads()
        self.assertEqual(('0000123','Synthetic Movie'),infos.tmdbid_to_imdbid('123'))
        self.assertEqual(('123','Synthetic Movie'),infos.imdbid_to_tmdbid('0000123'))
        result=infos.find_movie_ids('synthetic & query')
        self.assertEqual('Synthetic Movie (2020)',result[0]['label'])
        self.assertEqual('https://images.example.invalid/w92/synthetic.jpg',result[0]['poster'])
        paths=[]
        for raw,kwargs in self.calls:
            url=furl(raw);paths.append(str(url.path))
            self.assertEqual('https',url.scheme);self.assertEqual('api.themoviedb.org',url.host)
            self.assertEqual(KEY,url.args['api_key'])
            self.assertEqual(config.settings.searching.timeout,kwargs['timeout'])
            self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(['/3/movie/123','/3/find/tt0000123','/3/configuration','/3/search/movie'],paths)
        self.assertEqual('imdb_id',furl(self.calls[1][0]).args['external_source'])
        self.assertEqual('synthetic & query',furl(self.calls[-1][0]).args['query'])

    def test_rejected_redirect_and_server_errors_are_controlled(self):
        self.key();self.movie_payloads()
        for status in [301,302,401,403,429,500]:
            self.status=status
            self.assertEqual((None,None),infos.tmdbid_to_imdbid('123'))
            with self.assertRaises(infos.TmdbUnavailable) as caught:infos.find_movie_ids('synthetic')
            self.assertNotIn(KEY,str(caught.exception))

    def test_timeout_does_not_expose_exception_or_retry(self):
        self.key()
        def fail(url,**kwargs):
            self.calls.append(url);raise Timeout(KEY+' raw-sensitive-response')
        webaccess.get=fail
        self.assertEqual((None,None),infos.tmdbid_to_imdbid('123'))
        with self.assertRaises(infos.TmdbUnavailable) as caught:infos.find_movie_ids('synthetic')
        self.assertNotIn(KEY,str(caught.exception))
        self.assertNotIn('raw-sensitive-response',str(caught.exception))
        self.assertEqual(2,len(self.calls))

    def test_bad_response_shapes_and_empty_matches(self):
        self.key();self.movie_payloads()
        self.payloads['/3/configuration']={'images':{}}
        with self.assertRaises(infos.TmdbUnavailable):infos.find_movie_ids('synthetic')
        self.movie_payloads();self.payloads['/3/search/movie']={'results':[]}
        self.assertEqual([],infos.find_movie_ids('synthetic'))
        self.payloads['/3/movie/123']={'imdb_id':None,'title':'Synthetic'}
        self.assertEqual((None,None),infos.tmdbid_to_imdbid('123'))
        self.payloads['/3/find/tt0000123']={'movie_results':[]}
        self.assertEqual((None,None),infos.imdbid_to_tmdbid('0000123'))

    def test_identity_and_cached_conversion_need_no_credential(self):
        self.assertEqual('123',infos.convertId('tmdb','tmdb','123'))
        self.assertEqual('123',infos.convertId('tvdb','tvdb','123'))
        database.MovieIdCache.create(tmdb='123',imdb='0000123',title='Synthetic Cached')
        self.assertEqual('0000123',infos.convertId('tmdb','imdb','123'))
        self.assertEqual('Synthetic Cached',infos.convertId('tmdb','title','123'))
        self.assertEqual([],self.calls)

    def test_missing_conversion_does_not_poison_cache(self):
        self.assertIsNone(infos.convertId('tmdb','imdb','123'))
        self.assertEqual(0,database.MovieIdCache.select().count())
        self.key();self.movie_payloads()
        self.assertEqual('0000123',infos.convertId('tmdb','imdb','123'))

    def test_api_unavailable_is_503_and_not_cached_after_setup(self):
        response=self.autocomplete()
        self.assertEqual(503,response.status_code);self.assertIn(b'metadata',response.data)
        self.key();self.movie_payloads()
        response=self.autocomplete()
        self.assertEqual(200,response.status_code);self.assertIn(b'Synthetic Movie',response.data)
        self.assertNotIn(KEY.encode(),response.data)

    def test_movie_query_and_imdb_search_do_not_require_tmdb(self):
        web.startSearch=lambda request:web.jsonify({'query':request.query,'identifier_key':request.identifier_key})
        client=web.app.test_client()
        response=client.get('/internalapi/moviesearch?query=synthetic')
        self.assertEqual(200,response.status_code);self.assertIn(b'synthetic',response.data)
        response=client.get('/internalapi/moviesearch?imdbid=0000123')
        self.assertEqual(200,response.status_code);self.assertIn(b'imdbid',response.data)
        response=client.get('/internalapi/moviesearch?tmdbid=123')
        self.assertEqual(503,response.status_code)
        self.assertEqual([],self.calls)

    def test_unrelated_tv_autocomplete_is_preserved(self):
        self.payloads['/search/shows']=[{'show':{'externals':{'thetvdb':123},'name':'Synthetic TV','image':None}}]
        response=web.app.test_client().get('/internalapi/autocomplete?type=tv&input=synthetic')
        self.assertEqual(200,response.status_code);self.assertIn(b'Synthetic TV',response.data)
        self.assertEqual('api.tvmaze.com',furl(self.calls[0][0]).host)

    def test_new_secret_labels_are_masked_in_diagnostics(self):
        for key in ['NZBHYDRA_TMDB_API_KEY','tmdb_api_key','tmdbApiKey']:
            self.assertTrue(redaction.is_sensitive_key(key))
            self.assertNotIn(KEY,redaction.redact_text(key+'='+KEY))
            self.assertNotIn(KEY,config.getAnonymizedConfigSetting(key,KEY))

    def test_environment_and_key_file_never_enter_config_exports(self):
        self.key_file();self.key()
        for value in [config.getAnonymizedConfig(),config.getSafeConfig(),config.settings]:
            self.assertNotIn(KEY,json.dumps(value))


    def test_managed_log_formatter_masks_new_labels_and_request_urls(self):
        from nzbhydra import log
        for message in ['NZBHYDRA_TMDB_API_KEY='+KEY,
                        'https://api.themoviedb.org/3/movie/123?api_key='+KEY]:
            record=logging.LogRecord('synthetic',logging.ERROR,'synthetic.py',1,message,(),None)
            self.assertNotIn(KEY,log.console_logger.format(record))

    def test_debug_archive_excludes_environment_and_credential_file(self):
        import zipfile
        from nzbhydra import backup_debug,log
        self.key();self.key_file()
        previous_base=backup_debug.nzbhydra.getBasePath
        previous_logs=log.getAnonymizedLogFile
        backup_debug.nzbhydra.getBasePath=lambda:self.folder
        def synthetic_log(settings,path):
            with io.open(path,'w',encoding='utf8') as out:out.write('synthetic safe log')
        log.getAnonymizedLogFile=synthetic_log
        try:
            path=backup_debug.getDebuggingInfos()
            self.assertIsNotNone(path)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(set(['logfile.txt','settings.txt']),set(archive.namelist()))
                for name in archive.namelist():self.assertNotIn(KEY.encode(),archive.read(name))
        finally:
            backup_debug.nzbhydra.getBasePath=previous_base
            log.getAnonymizedLogFile=previous_logs

    def test_invalid_identifiers_do_not_send_requests(self):
        self.key()
        for value in [None,'','../unsafe','123/api_key=bad']:
            self.assertEqual((None,None),infos.tmdbid_to_imdbid(value))
            self.assertEqual((None,None),infos.imdbid_to_tmdbid(value))
        self.assertEqual([],self.calls)


if __name__=='__main__':unittest.main(verbosity=2)
