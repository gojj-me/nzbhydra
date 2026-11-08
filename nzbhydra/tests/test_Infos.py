import json
import re
import unittest

import mock
import pytest
import responses
import vcr

from nzbhydra import infos
from nzbhydra.database import init_db, TvIdCache, MovieIdCache
from nzbhydra.infos import find_movie_ids, tmdbid_to_imdbid


# TMDB cases moved to tests/test_metadata_credentials.py; remaining tapes are replay-only.
class TestInfos(unittest.TestCase):
    
    @pytest.fixture
    def setUp(self):
        init_db("tests.db")
        TvIdCache().delete().execute()




    @vcr.use_cassette('vcr/tvmaze2.yaml', record_mode='none')
    def testFindSeriesId(self):
        results = infos.find_series_ids("breaking bad")
        self.assertEqual(1, len(results))
        self.assertEqual("81189", results[0]["value"])
        self.assertEqual("Breaking Bad", results[0]["label"])
        self.assertEqual("http://tvmazecdn.com/uploads/images/medium_portrait/0/2400.jpg", results[0]["poster"])

    @vcr.use_cassette('vcr/omdb.yaml', record_mode='none')
    def testTitleFromId(self):
        title = infos.title_from_id("imdbid", "0169547")
        self.assertEqual("American Beauty", title)

    @vcr.use_cassette('vcr/tvmaze.yaml', record_mode='none')
    def testConvertTv(self):
        TvIdCache.delete().execute()
        id = infos.convertId("tvdb", "tvrage", "299350")
        self.assertEqual("47566", id)
        #This time from cache
        id = infos.convertId("tvdb", "tvrage", "299350")
        self.assertEqual("47566", id)
        
        TvIdCache.delete().execute()
        
        id = infos.convertId("tvdb", "tvmaze", "299350")
        self.assertEqual("3036", id)
        #This time from cache
        id = infos.convertId("tvdb", "tvmaze", "299350")
        self.assertEqual("3036", id)

        TvIdCache.delete().execute()
        id = infos.convertId("tvrage", "tvdb", "47566")
        self.assertEqual("299350", id)
        
        TvIdCache.delete().execute()
        id = infos.convertId("tvrage", "tvmaze", "47566")
        self.assertEqual("3036", id)
        
        TvIdCache.delete().execute()
        id = infos.convertId("tvmaze", "tvrage", "3036")
        self.assertEqual("47566", id)
        
        TvIdCache.delete().execute()
        id = infos.convertId("tvmaze", "tvdb", "3036")
        self.assertEqual("299350", id)


    def testCanConvertList(self):
        self.assertTrue(infos.canConvertList("tvrage", ["tvdb", "tvmaze"]))
        self.assertTrue(infos.canConvertList("tvdb", ["tvrage", "tvmaze"]))
        self.assertTrue(infos.canConvertList("tvmaze", ["tvrage", "tvdbid"]))
        self.assertTrue(infos.canConvertList("imdb", ["tmdb"]))
        self.assertTrue(infos.canConvertList("tmdb", ["imdb"]))

    @vcr.use_cassette('vcr/tvmaze.yaml', record_mode='none')
    def testConvertToAny(self):
        canConvert, toType, id = infos.convertIdToAny("tvmaze", ["rid", "tvdb"], "3036")
        self.assertTrue(canConvert)
        self.assertEqual(toType, "tvrage")
        self.assertEqual("47566", id)

        canConvert, toType, id = infos.convertIdToAny("tvrage", ["tvmaze", "tvdb"], "47566")
        self.assertTrue(canConvert)
        self.assertEqual(toType, "tvmaze")
        self.assertEqual("3036", id)

        canConvert, toType, id = infos.convertIdToAny("tvrage", ["tvdbid", "tvmazeid"], "47566")
        self.assertTrue(canConvert)
        self.assertEqual(toType, "tvdb")
        self.assertEqual("299350", id)

        canConvert, toType, id = infos.convertIdToAny("tvmaze", ["imdbid", "tmdb"], "3036")
        self.assertFalse(canConvert)



        
        

    @vcr.use_cassette('vcr/tvmaze.yaml', record_mode='none')
    def testGetTvTitle(self):
        TvIdCache.delete().execute()
        id = infos.convertId("tvdb", "title", "299350")
        self.assertEqual("Casual", id)
        # This time from cache
        id = infos.convertId("tvdb", "title", "299350")
        self.assertEqual("Casual", id)

        TvIdCache.delete().execute()

        id = infos.convertId("tvdb", "title", "299350")
        self.assertEqual("Casual", id)
        # This time from cache
        id = infos.convertId("tvdb", "title", "299350")
        self.assertEqual("Casual", id)

        TvIdCache.delete().execute()
        id = infos.convertId("tvrage", "title", "47566")
        self.assertEqual("Casual", id)

        TvIdCache.delete().execute()
        id = infos.convertId("tvrage", "title", "47566")
        self.assertEqual("Casual", id)

        TvIdCache.delete().execute()
        id = infos.convertId("tvmaze", "title", "3036")
        self.assertEqual("Casual", id)

        TvIdCache.delete().execute()
        id = infos.convertId("tvmaze", "title", "3036")
        self.assertEqual("Casual", id)

    @vcr.use_cassette('vcr/tvmaze3.yaml', record_mode='none')
    def testGetTvTitleDoesntExist(self):
        TvIdCache.delete().execute()
        id = infos.convertId("tvdb", "title", "299350000")
        self.assertIsNone(id)
        