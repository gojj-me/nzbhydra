"""NZBIndex details/NFO and actual Hydra API regression, invented data only."""
from __future__ import print_function
import os,sys,tempfile,shutil,json,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0]=[ROOT,ROOT+'/libs']
from bunch import Bunch
from requests import Response
from requests.exceptions import Timeout
from nzbhydra import config,database,indexers
from nzbhydra.searchmodules.nzbindex import NzbIndex


class NzbIndexDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.mkdtemp(prefix='hydra-details-test-')
        database.init_db(cls.folder+'/synthetic.db')
        config.settings=Bunch.fromDict(config.initialConfig)
        global web
        from nzbhydra import web
        web.app.template_folder=os.path.join(ROOT,"templates")
        cls.indexer=database.Indexer.create(name='synthetic')

    @classmethod
    def tearDownClass(cls):
        database.db.stop();database.db.close();shutil.rmtree(cls.folder)

    def setUp(self):
        config.settings=Bunch.fromDict(config.initialConfig)
        config.settings.main.apikey='invented-api-key'
        self.module=NzbIndex(Bunch(name='synthetic',host='https://example.invalid',score=0,timeout=1))
        indexers.enabled_indexers=[self.module]
        indexers.configured_indexers=[self.module]
        for model in (database.IndexerApiAccess,database.IndexerStatus,database.SearchResult):
            model.delete().execute()
        self.row={'id':'synthetic-guid','name':'Synthetic.Refreshed.mkv','size':1234567,
                  'posted':1700000000,'poster':'synthetic','groups':['alt.test'],'files':[]}
        self.calls=[]
        self.payload={'error':False,'data':self.row}
        self.code=200
        def get(url,**kwargs):
            self.calls.append(url)
            response=Response();response.status_code=self.code;response.url=url
            response._content=(self.payload if isinstance(self.payload,str) else json.dumps(self.payload)).encode('utf8')
            return response
        self.module.get=get

    def refresh(self,guid='synthetic-guid'):
        return self.module.get_entry_by_id(guid,'obsolete caller title')

    def record(self):
        return database.SearchResult.create(id='hydra-id',indexer=self.indexer,
            guid='synthetic-guid',title='old title',link='https://example.invalid/download/synthetic-guid.nzb')

    def test_fresh_metadata_and_current_request(self):
        entry=self.refresh()
        self.assertEqual(['https://example.invalid/api/collection/synthetic-guid'],self.calls)
        self.assertEqual('synthetic-guid',entry.indexerguid)
        self.assertEqual('Synthetic.Refreshed',entry.title)
        self.assertEqual(1234567,entry.size);self.assertEqual(1700000000,entry.epoch)
        self.assertEqual('synthetic',entry.poster);self.assertEqual('alt.test',entry.group)
        self.assertEqual('https://example.invalid/collection/synthetic-guid',entry.details_link)
        self.assertEqual('https://example.invalid/download/synthetic-guid.nzb',entry.link)
        self.assertTrue(database.IndexerApiAccess.get().response_successful)
        self.assertEqual('details',database.IndexerApiAccess.get().type)

    def test_provider_declared_error_or_absent_data(self):
        for payload in [{'error':True,'data':None,'errorMessage':'invented-provider-private'},
                        {'error':False,'data':None}]:
            database.IndexerApiAccess.delete().execute()
            self.payload=payload
            self.assertIsNone(self.refresh())
            self.assertFalse(database.IndexerApiAccess.get().response_successful)
            self.assertNotIn('invented-provider-private',database.IndexerApiAccess.get().error)

    def test_malformed_json_html_and_metadata(self):
        for payload in ['{invalid','<html>invented-sensitive-page</html>',{'data':self.row},
                        {'error':False,'data':{}}, {'error':False,'data':dict(self.row,id='other-guid')}]:
            self.payload=payload
            self.assertIsNone(self.refresh())

    def test_deleted_and_failed_provider_response(self):
        for code in [404,500,503]:
            self.code=code;self.assertIsNone(self.refresh())
            self.assertFalse(self.module.indexer.status.get().disabled_permanently)

    def test_request_timeout_is_controlled(self):
        def fail(*args,**kwargs):raise Timeout('synthetic timeout')
        self.module.get=fail
        self.assertIsNone(self.refresh())
        self.assertFalse(database.IndexerApiAccess.get().response_successful)

    def test_invalid_id_sends_no_request(self):
        for guid in [None,'../unsafe','',3]:
            self.assertIsNone(self.refresh(guid))
        self.assertEqual([],self.calls)

    def test_nfo_unavailable_without_a_network_call(self):
        found,body,message=self.module.get_nfo('synthetic-guid')
        self.assertFalse(found);self.assertIsNone(body);self.assertIn('unavailable',message)
        self.assertEqual([],self.calls)
        self.assertEqual(0,database.IndexerApiAccess.select().count())
        self.assertEqual(0,database.IndexerStatus.select().count())
        self.assertEqual(0,self.module.parse_json_row(self.row).has_nfo)

    def test_actual_api_details_rewrites_download_to_hydra(self):
        self.record()
        response=web.app.test_client().get('/api?t=details&id=hydra-id&apikey=invented-api-key')
        self.assertEqual(200,response.status_code)
        self.assertIn(b'Synthetic.Refreshed',response.data)
        self.assertIn(b'getnzb',response.data)
        self.assertIn(b'apikey=invented-api-key',response.data)
        self.assertIn(b'<category>N/A</category>',response.data)
        self.assertIn(b'<guid isPermaLink="false">hydra-id</guid>',response.data)
        self.assertNotIn(b'https://example.invalid/download/',response.data)

    def test_actual_api_json_details_preserves_identity_and_link(self):
        self.record()
        response=web.app.test_client().get('/api?t=details&id=hydra-id&apikey=invented-api-key&o=json')
        self.assertEqual(200,response.status_code)
        item=json.loads(response.data)['channel']['item'][0]
        self.assertEqual('hydra-id',item['guid'])
        self.assertEqual('N/A',item['category'])
        self.assertIn('getnzb',item['link'])
        self.assertIn('searchresultid=hydra-id',item['link'])
        self.assertIn('apikey=invented-api-key',item['link'])

    def test_details_rejects_unknown_output_format(self):
        self.record()
        response=web.app.test_client().get('/api?t=details&id=hydra-id&apikey=invented-api-key&o=unsupported')
        self.assertEqual(500,response.status_code)
        self.assertEqual([],self.calls)

    def test_actual_api_nfo_returns_error_for_raw_and_html_modes(self):
        self.record()
        for raw in [0,1]:
            response=web.app.test_client().get('/api?t=getnfo&id=hydra-id&apikey=invented-api-key&raw='+str(raw))
            self.assertEqual(200,response.status_code)
            self.assertIn(b'<error',response.data)
            self.assertIn(b'NFO retrieval unavailable',response.data)
        self.assertEqual([],self.calls)

    def test_api_authentication_still_required(self):
        response=web.app.test_client().get('/api?t=details&id=hydra-id')
        self.assertNotEqual(200,response.status_code)
        self.assertEqual([],self.calls)


if __name__=='__main__':unittest.main(verbosity=2)
