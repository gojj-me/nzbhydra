from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import open
from future import standard_library
#standard_library.install_aliases()
from builtins import *
import unittest
from freezegun import freeze_time

from furl import furl
import pytest
from nzbhydra import config

from nzbhydra.exceptions import IndexerResultParsingException
from nzbhydra.database import Indexer
from nzbhydra.indexers import getIndexerSettingByName
from nzbhydra.search import SearchRequest
from nzbhydra.searchmodules.binsearch import Binsearch
from nzbhydra.tests.UrlTestCase import UrlTestCase
from nzbhydra.tests.db_prepare import set_and_drop


class TestBinsearch(UrlTestCase):
    
    @pytest.fixture
    def setUp(self):
        set_and_drop()
    

    def testUrlGeneration(self):
        w = Binsearch(getIndexerSettingByName("binsearch"))
        self.args = SearchRequest(query="a showtitle", season=1, episode=2)
        urls = w.get_showsearch_urls(self.args)
        self.assertEqual(2, len(urls))
        self.assertEqual('a showtitle s01e02', furl(urls[0]).args["q"])
        self.assertEqual('a showtitle 1x02', furl(urls[1]).args["q"])

        self.args = SearchRequest(query="a showtitle", season=1, episode=None)
        urls = w.get_showsearch_urls(self.args)
        self.assertEqual(2, len(urls))
        self.assertEqual('a showtitle s01', furl(urls[0]).args["q"])
        self.assertEqual('a showtitle "season 1"', furl(urls[1]).args["q"])

        self.args = SearchRequest(query="a showtitle", season=2016, episode="08/08")
        urls = w.get_showsearch_urls(self.args)
        self.assertEqual(1, len(urls))
        self.assertEqual('a showtitle "2016 08 08"', furl(urls[0]).args["q"])
        
    def testEbookUrlGeneration(self):
        getIndexerSettingByName("binsearch").searchTypes = []
        w = Binsearch(getIndexerSettingByName("binsearch"))
        self.args = SearchRequest(query="anauthor atitle")
        urls = w.get_ebook_urls(self.args)
        self.assertEqual(4, len(urls))
        self.assertEqual("https://binsearch.info/search?page=0&q=anauthor+atitle+ebook", urls[0])
        self.assertEqual("https://binsearch.info/search?page=0&q=anauthor+atitle+mobi", urls[1])

        self.args = SearchRequest(author="anauthor", title="atitle")
        urls = w.get_ebook_urls(self.args)
        self.assertEqual(4, len(urls))
        self.assertEqual("https://binsearch.info/search?page=0&q=anauthor+atitle+ebook", urls[0])
        self.assertEqual("https://binsearch.info/search?page=0&q=anauthor+atitle+mobi", urls[1])
        
        

    def testRetiredLayoutsFailExplicitly(self):
        # Historical fixtures remain for provenance; their contract is retired.
        # Current synthetic contract regressions live in tests/test_binsearch.py.
        w = Binsearch(getIndexerSettingByName("binsearch"))
        for fixture in ("mock/binsearch--q-testtitle.html", "mock/binsearch--q-testtitle3results.html"):
            with open(fixture, encoding="latin-1") as f:
                with self.assertRaises(IndexerResultParsingException):
                    w.process_query_result(f.read(), SearchRequest())

    def testGetNzbLink(self):
        n = Binsearch(getIndexerSettingByName("binsearch"))
        link = n.get_nzb_link("guid", "title")
        assert str(furl(link).path) == "/nzb"
        assert dict(furl(link).args) == {"id": "guid"}
        
