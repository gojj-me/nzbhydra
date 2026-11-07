"""Current Binsearch contract, synthetic HTML only; Python 2.7, no network."""
from __future__ import print_function, unicode_literals
import os,sys,tempfile,shutil,unittest,urlparse
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0]=[ROOT,ROOT+'/libs']
from bunch import Bunch
from furl import furl
from requests import Response
from requests.exceptions import Timeout
from nzbhydra import config,categories,database,indexers,search
from nzbhydra.searchmodules.binsearch import Binsearch
from nzbhydra.exceptions import IndexerResultParsingException

GUID='MDAwMDAwMDAtMDAwMC0wMDAwLTAwMDAtMDAwMDAwMDAwMDAx'
def row(guid=GUID,title='Synthetic.Release.mkv',size='1.5GB',age='4 days'):
    return ('<tr><td>1.</td><td><input type="checkbox" name="'+guid+'"/></td>'
            '<td><div><a href="/details/'+guid+'">'+title+'</a><div><span>'+size+'</span>'
            '<span>1 complete file</span><a href="/search?poster=poster%40example.invalid">poster</a>'
            '<a href="/search?group=alt.test">alt.test</a></div></div></td><td>'+age+'</td></tr>')
def page(rows=None,number=0,more=False):
    return ('<html><title>Binsearch - Search</title><form action="/nzb" method="GET">'
            '<input name="q" type="hidden" value="synthetic"/><table class="result-table">'
            '<tr><th>Subject</th><th>Age</th></tr>'+(''.join(rows) if rows is not None else row())+
            '</table></form><ul aria-label="Pagination"><a aria-current="page">'+str(number+1)+
            '</a><a aria-label="Next page" aria-disabled="'+('false' if more else 'true')+'">Next</a></ul></html>')
def details(guid=GUID):
    return ('<html><title>Binsearch - Details</title><form action="/nzb" method="GET">'
            '<input name="name" value="Synthetic.Refreshed.mkv"/><input name="id" value="'+guid+'"/>'
            '<table class="result-table"><tr><th>Subject</th><th>Age</th></tr>'
            '<tr><td></td><td>synthetic.mkv<span>Parts: 2 / 2</span><span>1MB</span></td><td>4 days</td></tr>'
            '<tr><td></td><td>synthetic.par2<span>Parts: 1 / 1</span><span>2MB</span></td><td>5 days</td></tr>'
            '</table></form></html>')



def setUpModule():
    global test_folder
    test_folder=tempfile.mkdtemp(prefix='hydra-binsearch-test-')
    database.init_db(test_folder+'/synthetic.db')
    database.Indexer.create(name='synthetic')

def tearDownModule():
    database.db.stop();database.db.close();shutil.rmtree(test_folder)


class BinsearchTests(unittest.TestCase):
    def setUp(self):
        config.settings=Bunch.fromDict(config.initialConfig)
        self.module=Binsearch(Bunch(name='synthetic',host='https://example.invalid',timeout=1,score=0,categories=[]))
        self.request=search.SearchRequest(type='general',query='synthetic',category=categories.getCategoryByAnyInput(None))
        self.calls=[];self.body=details();self.code=200
        database.IndexerStatus.delete().execute();database.IndexerApiAccess.delete().execute()
        def get(url,**kwargs):
            self.calls.append(url)
            response=Response();response.status_code=self.code;response.url=url
            response._content=self.body.encode('utf8')
            return response
        self.module.get=get
    def parse(self,body):return self.module.process_query_result(body,self.request)

    def test_search_query_and_only_supported_remote_parameters(self):
        self.request.query='synthetic & title + \u00e5'
        self.request.offset=25;self.request.minsize=1;self.request.maxsize=2;self.request.maxage=7
        url=furl(self.module.get_search_urls(self.request)[0])
        self.assertEqual('/search',str(url.path))
        raw=self.module.get_search_urls(self.request)[0]
        self.assertEqual(self.request.query,urlparse.parse_qs(urlparse.urlsplit(raw.encode('ascii')).query)['q'][0].decode('utf8'))
        self.assertEqual('1',str(url.args['page']));self.assertEqual(set(['q','page']),set(url.args))
        self.assertEqual(25,self.module.limit)

    def test_show_and_ebook_query_variants(self):
        self.request.season=1;self.request.episode=2
        urls=self.module.get_showsearch_urls(self.request)
        self.assertEqual(['synthetic s01e02','synthetic 1x02'],[furl(x).args['q'] for x in urls])
        self.request.query='synthetic'
        urls=self.module.get_ebook_urls(self.request)
        self.assertEqual(['synthetic '+x for x in ['ebook','mobi','pdf','epub']],[furl(x).args['q'] for x in urls])
        self.assertTrue(all(str(furl(x).path)=='/search' for x in urls))

    def test_success_metadata_and_single_collection_links(self):
        entry=self.parse(page()).entries[0]
        self.assertEqual(GUID,entry.indexerguid);self.assertEqual('Synthetic.Release',entry.title)
        self.assertEqual(1610612736,entry.size);self.assertEqual(4,entry.age_days)
        self.assertFalse(entry.age_precise);self.assertIsNotNone(entry.pubDate)
        self.assertEqual('poster@example.invalid',entry.poster);self.assertEqual('alt.test',entry.group)
        url=furl(entry.link)
        self.assertEqual('/nzb',str(url.path));self.assertEqual({'id':GUID},dict(url.args))
        self.assertEqual('https://example.invalid/details/'+GUID,entry.details_link)
        self.assertEqual(0,entry.has_nfo)

    def test_sizes_and_relative_ages(self):
        for text,value in [('2B',2),('1KB',1024),('2.5 MB',2621440),('1GB',1073741824),('1TB',1099511627776)]:
            self.assertEqual(value,self.module.parse_size(text))
        for text in ['1 second','2 minutes','1 hour','3 days','1 week','2 months','1 year','just now']:
            self.assertIsNotNone(self.module.parse_age(text))
        for text in ['yesterday','-1 days','private contents']:
            with self.assertRaises(ValueError):self.module.parse_age(text)

    def test_empty_is_valid_and_stops_even_if_next_is_enabled(self):
        result=self.parse(page([],more=True))
        self.assertEqual([],result.entries);self.assertFalse(result.has_more)
        self.assertEqual(0,result.total)

    def test_pagination_and_nonadvancing_response(self):
        self.assertTrue(self.parse(page(more=True)).has_more)
        self.request.offset=25
        self.assertFalse(self.parse(page(number=1)).has_more)
        with self.assertRaises(IndexerResultParsingException):self.parse(page(more=True))

    def test_unexpected_layout_is_not_empty(self):
        for body in [None,'','<html>challenge</html>','<title>Binsearch</title>',
                     page().replace('result-table','unknown'),page().replace('aria-label="Pagination"',''),
                     page().replace('aria-disabled="true"','aria-disabled="unknown"')]:
            with self.assertRaises(IndexerResultParsingException):self.parse(body)

    def test_malformed_rows_fail_without_dumping_response(self):
        for body in [page([row(size='private-response')]),page([row(age='private-response')]),
                     page([row(guid='../unsafe')]),page([row(),row()]),page([row()]*26),
                     page([row()]).replace('/details/'+GUID,'/details/other')]:
            with self.assertRaises(IndexerResultParsingException) as caught:self.parse(body)
            self.assertNotIn('private-response',str(caught.exception))

    def test_local_size_and_age_filters(self):
        for field,value in [('minsize',1600),('maxsize',1000),('minage',5),('maxage',3)]:
            request=search.SearchRequest(type='general',query='synthetic',category=categories.getCategoryByAnyInput(None))
            setattr(request,field,value)
            result=self.module.process_query_result(page(),request)
            self.assertEqual([],result.entries);self.assertEqual(1,sum(result.rejected.values()))
        self.request.minsize=1536;self.request.maxsize=1536;self.request.minage=4;self.request.maxage=4
        self.assertEqual(1,len(self.parse(page()).entries))

    def test_all_filtered_page_still_advances(self):
        self.request.minsize=2000
        result=self.parse(page(more=True))
        self.assertEqual([],result.entries);self.assertTrue(result.has_more)

    def test_details_refresh_sums_files_and_preserves_identity(self):
        entry=self.module.get_entry_by_id(GUID,'obsolete')
        self.assertEqual(['https://example.invalid/details/'+GUID],self.calls)
        self.assertEqual('Synthetic.Refreshed',entry.title);self.assertEqual(GUID,entry.indexerguid)
        self.assertEqual(3*1024*1024,entry.size);self.assertEqual(5,entry.age_days)
        self.assertTrue(database.IndexerApiAccess.get().response_successful)

    def test_details_failure_missing_and_wrong_identity(self):
        for body in ['<html>private-response</html>',details('wrong-id'),details().replace('1MB','unknown')]:
            self.body=body
            self.assertIsNone(self.module.get_entry_by_id(GUID,None))
            self.assertFalse(database.IndexerApiAccess.select().order_by(database.IndexerApiAccess.id.desc()).get().response_successful)
        for code in [404,500,503]:
            self.code=code;self.assertIsNone(self.module.get_entry_by_id(GUID,None))

    def test_timeout_and_invalid_identifier_are_controlled(self):
        def fail(*args,**kwargs):raise Timeout('synthetic timeout')
        self.module.get=fail
        self.assertIsNone(self.module.get_entry_by_id(GUID,None))
        for guid in [None,'','../unsafe',3,'x&action=nzb']:
            self.assertIsNone(self.module.get_entry_by_id(guid,None))
        self.assertEqual([],self.calls)

    def test_nfo_unavailable_without_retired_network_request(self):
        found,body,message=self.module.get_nfo(GUID)
        self.assertFalse(found);self.assertIsNone(body);self.assertIn('unavailable',message)
        self.assertEqual([],self.calls)

    def test_search_http_failure_is_not_successful_empty(self):
        for code,body,success in [(200,page([]),True),(200,'<html>challenge</html>',False),
                                  (403,'<html>denied</html>',False),(404,'missing',False),(503,'unavailable',False)]:
            self.code,self.body=code,body
            result=self.module.execute_queries(self.module.get_search_urls(self.request),self.request)
            self.assertEqual(success,result.indexerSearchEntry.successful)
            self.assertFalse(result.has_more)
            self.assertEqual([],result.results)
        self.assertTrue(all(str(furl(url).path)=='/search' for url in self.calls))

    def test_actual_api_details_and_nfo(self):
        from nzbhydra import web
        web.app.template_folder=ROOT+'/templates'
        config.settings.main.apikey='invented-api-key'
        indexers.enabled_indexers=[self.module];indexers.configured_indexers=[self.module]
        database.SearchResult.delete().execute()
        database.SearchResult.create(id='synthetic-hydra-id',indexer=self.module.indexer,guid=GUID,
                                     title='obsolete',link=self.module.get_nzb_link(GUID,None))
        # Non-auto primary-key inserts are queued without awaiting lastrowid.
        # Await the writer before the independent API reader checks this fixture.
        database.db.execute_sql("SELECT 1", require_commit=True).fetchone()
        client=web.app.test_client()
        response=client.get('/api?t=details&id=synthetic-hydra-id&apikey=invented-api-key')
        self.assertEqual(200,response.status_code);self.assertIn(b'Synthetic.Refreshed',response.data)
        self.assertIn(b'getnzb',response.data)
        for raw in [0,1]:
            response=client.get('/api?t=getnfo&id=synthetic-hydra-id&apikey=invented-api-key&raw='+str(raw))
            self.assertIn(b'<error',response.data);self.assertIn(b'unavailable',response.data)
        before=len(self.calls)
        response=client.get('/api?t=details&id=synthetic-hydra-id')
        self.assertNotEqual(200,response.status_code);self.assertEqual(before,len(self.calls))


class BinsearchPaginationTests(unittest.TestCase):
    def setUp(self):
        config.settings=Bunch.fromDict(config.initialConfig)
        search.pseudo_cache.clear()
        self.module=Binsearch(Bunch(name='synthetic',host='https://example.invalid',timeout=1,score=0,categories=[]))
        self.originals=(search.pick_indexers,search.search_and_handle_db,search.retention_cleaner.schedule,
                        search.tryGetOrCreateSearchResultDbEntry,search.find_duplicates)
        search.pick_indexers=lambda request:[self.module]
        search.retention_cleaner.schedule=lambda *args:False
        search.tryGetOrCreateSearchResultDbEntry=lambda *args:None
        search.find_duplicates=lambda results:([[entry] for entry in results],{})
        self.pages=[];self.last_page=5
        def execute(dbsearch,requests):
            request=requests[self.module]
            number=request.offset//self.module.limit;self.pages.append(number)
            rows=[]
            for i in range(25):
                entry=self.module.result_metadata('synthetic-%d-%d'%(number,i),'Synthetic.%d.%d'%(number,i))
                entry.size=1000000
                self.module.getDates(entry,self.module.parse_age('4 days'),False)
                rows.append(entry)
            result=Bunch(results=rows,didsearch=True,has_more=number<self.last_page,total=25,total_known=number==self.last_page,
                         indexerSearchEntry=None,rejected={},loaded_results=25)
            return {'results':{self.module:result}}
        search.search_and_handle_db=execute
    def tearDown(self):
        (search.pick_indexers,search.search_and_handle_db,search.retention_cleaner.schedule,
         search.tryGetOrCreateSearchResultDbEntry,search.find_duplicates)=self.originals
    def run_search(self,offset=0,limit=100):
        return search.search(search.SearchRequest(type='general',query='synthetic',offset=offset,limit=limit))
    def test_large_api_limit_does_not_skip_provider_pages(self):
        result=self.run_search()
        self.assertEqual([0,1,2,3],self.pages)
        self.assertEqual(100,result['total'])
    def test_cached_cursor_survives_changed_api_limit(self):
        self.run_search(limit=10)
        self.run_search(offset=10,limit=40)
        self.assertEqual([0,1],self.pages)
    def test_new_search_resets_cursor_and_exhaustion_stops(self):
        self.last_page=1
        result=self.run_search();self.assertEqual([0,1],self.pages)
        self.assertEqual(50,result['total'])
        self.run_search();self.assertEqual([0,1,0,1],self.pages)


    def test_identifier_fallback_resets_provider_cursor(self):
        original_execute=search.search_and_handle_db
        original_convert=search.infos.convertId
        search.infos.convertId=lambda *args:'Synthetic fallback'
        config.settings.searching.idFallbackToTitle=['internal']
        config.settings.searching.idFallbackToTitlePerIndexer=False
        seen=[]
        def execute(dbsearch,requests):
            request=requests[self.module]
            if request.identifier_key is not None:
                seen.append(request.offset)
                return {'results':{self.module:Bunch(results=[],didsearch=True,has_more=False,
                    total=0,total_known=True,indexerSearchEntry=None,rejected={},loaded_results=0)}}
            seen.append(request.offset)
            return original_execute(dbsearch,requests)
        search.search_and_handle_db=execute
        try:
            self.last_page=0
            search.search(search.SearchRequest(type='movie',identifier_key='imdbid',identifier_value='0000001'))
            self.assertEqual([0,0],seen)
        finally:search.infos.convertId=original_convert

    def test_other_indexers_keep_existing_offset_semantics(self):
        self.module.uses_page_numbers=False
        self.run_search()
        self.assertEqual([0,4,8],self.pages)


if __name__=='__main__':unittest.main(verbosity=2)
