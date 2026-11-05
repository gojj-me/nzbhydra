"""Synthetic NZBIndex response and request-contract regressions, no providers."""
from __future__ import print_function
import os,sys,json,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0]=[ROOT,ROOT+'/libs']
from bunch import Bunch
from furl import furl
from nzbhydra import config,webaccess
from nzbhydra.search import SearchRequest
from nzbhydra.searchmodules.nzbindex import NzbIndex
from nzbhydra.exceptions import IndexerResultParsingException


class NzbIndexTests(unittest.TestCase):
    def setUp(self):
        config.settings=Bunch.fromDict(config.initialConfig)
        self.module=NzbIndex(Bunch(name='synthetic',host='https://example.invalid',generalMinSize=0,timeout=2,score=0))
        self.module.accept_result=lambda *args:(True,None,None)
        self.request=SearchRequest(type='general',query='synthetic',forbiddenWords=['unwanted'])
        self.row={'id':'synthetic-123','name':'Synthetic.Test.mkv','size':123456789,
                  'posted':1700000000,'poster':'synthetic','groups':['alt.test'],'complete':True}
    def body(self,rows=None,number=0,pages=1,total=None):
        rows=[dict(self.row)] if rows is None else rows
        return json.dumps({'error':False,'errorMessage':'','data':{'content':rows,'page':{
            'number':number,'totalPages':pages,'totalElements':len(rows) if total is None else total}}})
    def parse(self,value):return self.module.process_query_result(value,self.request)

    def test_missing_container_is_controlled(self):
        for body in ['<html/>','<html><title>NZBIndex</title><div id="results"/></html>',
                     '<div id="results"><table/></div>','<html><h1>Challenge</h1></html>','',None,'{bad json','[]']:
            with self.assertRaises(IndexerResultParsingException):self.parse(body)

    def test_legitimate_empty_html_without_table(self):
        result=self.parse('<html><title>NZBIndex</title><p>No results found</p></html>')
        self.assertEqual([],result.entries);self.assertEqual(0,result.total);self.assertFalse(result.has_more)

    def test_empty_message_in_script_or_unbranded_page_is_not_success(self):
        for body in ['<title>NZBIndex</title><script>No results found</script>',
                     '<p>No results found</p>']:
            with self.assertRaises(IndexerResultParsingException):self.parse(body)

    def test_json_metadata_and_links(self):
        entry=self.parse(self.body()).entries[0]
        self.assertEqual('synthetic-123',entry.indexerguid)
        self.assertEqual(123456789,entry.size)
        self.assertEqual(1700000000,entry.epoch)
        self.assertTrue(entry.age_precise);self.assertIsNotNone(entry.pubDate)
        self.assertEqual('Synthetic.Test',entry.title)
        self.assertEqual('alt.test',entry.group)
        self.assertEqual('https://example.invalid/download/synthetic-123.nzb',entry.link)
        self.assertEqual('https://example.invalid/collection/synthetic-123',entry.details_link)

    def test_json_empty_and_pagination(self):
        result=self.parse(self.body([],pages=1,total=0))
        self.assertEqual(0,result.total);self.assertFalse(result.has_more)
        self.assertTrue(self.parse(self.body(pages=2,total=2)).has_more)
        self.assertFalse(self.parse(self.body(number=1,pages=2,total=2)).has_more)

    def test_bad_envelopes_and_provider_errors(self):
        for value in [{'error':True,'errorMessage':'invented-private-response'},
                      {'error':False,'data':{}}, {'data':{'content':[]}},
                      {'error':False,'data':{'content':[],'page':{'number':0,'totalPages':1,'totalElements':5}}}]:
            with self.assertRaises(IndexerResultParsingException) as error:self.parse(json.dumps(value))
            self.assertNotIn('invented-private-response',str(error.exception))

    def test_bad_rows(self):
        for key,value in [('id','../unsafe'),('name',None),('size',-1),('posted',True),('groups',None)]:
            row=dict(self.row);row[key]=value
            with self.assertRaises(IndexerResultParsingException):self.parse(self.body([row]))

    def test_filters_reach_request(self):
        self.request.offset=100;self.request.minsize=500;self.request.maxsize=2000
        self.request.minage=1;self.request.maxage=7
        url=furl(self.module.get_search_urls(self.request)[0])
        self.assertEqual('/api/search',str(url.path))
        for key,value in [('page','1'),('max','100'),('minsize','500'),('maxsize','2000'),('minage','1'),('maxage','7')]:
            self.assertEqual(value,str(url.args[key]))
        self.assertEqual('synthetic -unwanted',url.args['q'])

    def test_general_size_and_first_page(self):
        self.module.settings.generalMinSize=123
        url=furl(self.module.get_search_urls(self.request)[0])
        self.assertEqual('123',str(url.args['minsize']))
        self.assertNotIn('page',url.args)

    def test_timeout_defaults_are_preserved(self):
        original=webaccess.get;calls=[]
        webaccess.get=lambda url,**kwargs:calls.append((url,kwargs))
        try:self.module.get('https://example.invalid/api/search?q=synthetic')
        finally:webaccess.get=original
        self.assertEqual(2,calls[0][1]['timeout'])

    def test_result_restrictions_are_applied(self):
        self.module.accept_result=lambda *args:(False,'synthetic rejection','passworded')
        # Use a real rejection counter name from the application's dictionary.
        key=list(self.module.getRejectedCountDict())[0]
        self.module.accept_result=lambda *args:(False,'synthetic rejection',key)
        result=self.parse(self.body())
        self.assertEqual([],result.entries);self.assertEqual(1,result.rejected[key])

    def test_legacy_valid_row_and_malformed_row(self):
        row='<tr><td><input value="123"/></td><td><label>"Synthetic.Test.mkv"</label><span class="poster"><a>synthetic</a></span><a href="https://example.invalid/download/123.nzb">Download</a></td><td>1.0 MB</td><td>alt.test</td><td>1.0</td></tr>'
        result=self.parse('<div id="results"><table><tbody>'+row+'</tbody></table></div>')
        self.assertEqual('123',result.entries[0].indexerguid)
        self.assertEqual(1048576,result.entries[0].size)
        with self.assertRaises(IndexerResultParsingException):
            self.parse('<div id="results"><table><tbody><tr>'+('<td>missing</td>'*5)+'</tr></tbody></table></div>')


if __name__=='__main__':unittest.main(verbosity=2)
