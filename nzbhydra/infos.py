from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import arrow
from future import standard_library
from peewee import IntegrityError
from requests import RequestException

#standard_library.install_aliases()
from builtins import *
import logging
import re
from six import string_types
import requests
import pytvmaze
from furl import furl
from enum import Enum
from requests.exceptions import ReadTimeout
from requests.packages.urllib3.exceptions import HTTPError, ConnectionError

from nzbhydra import webaccess, config
from nzbhydra.metadata_credentials import tmdb_api_key, MetadataCredentialUnavailable
from nzbhydra.exceptions import ExternalApiInfoException
from nzbhydra.database import TvIdCache, MovieIdCache

logger = logging.getLogger('root')

class TmdbUnavailable(ExternalApiInfoException):
    pass


def _tmdb_json(path, params=None):
    try:
        key = tmdb_api_key()
    except MetadataCredentialUnavailable:
        raise TmdbUnavailable("TMDB metadata is unavailable; configure an operator-supplied API key.")
    url = furl("https://api.themoviedb.org/3/" + path)
    url.add(dict(params or {}, api_key=key))
    try:
        response = webaccess.get(url.tostr(), timeout=config.settings.searching.timeout, allow_redirects=False)
        if response.status_code != 200:
            raise ValueError()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("success") is False:
            raise ValueError()
        return payload
    except (RequestException, ValueError, TypeError):
        # No provider body, URL, exception text or credential enters this error.
        raise TmdbUnavailable("TMDB metadata is unavailable; check provider access and credentials.")


class TvMaze:
    
    def __init__(self, tvmazeid, rageid, tvdbid, title, poster):
        self.tvmazeid = tvmazeid
        self.rageid = rageid
        self.tvdbid = tvdbid
        self.title = title
        self.poster = poster
     

    @staticmethod
    def byId(idType, id):
        logger.info("Requesting info for %s key %s from TVMaze" % (idType, id))
        try:
            if idType == "thetvdb":
                info = pytvmaze.get_show(tvdb_id=id)
            elif idType == "tvrage":
                info = pytvmaze.get_show(tvrage_id=id)
            elif idType == "tvmaze":
                info = pytvmaze.get_show(maze_id=id)
            else:
                logger.error("Invalid call to byId() using idType %s" % idType)
                return None
            
        except pytvmaze.ShowNotFound:
            logger.error("Unable to find show on TVMaze")
            return None
        externals = info.externals
        rageid = externals["tvrage"] if "tvrage" in externals.keys() else None
        tvdbid = externals["thetvdb"] if "thetvdb" in externals.keys() else None
        title = info.name
        poster = info.image["medium"] if "medium" in info.image.keys() else None
        return TvMaze(info.id, rageid, tvdbid, title, poster)


def find_movie_ids(input):
    try:
        images = _tmdb_json("configuration")["images"]
        base_url = images["secure_base_url"]
        sizes = images["poster_sizes"]
        poster_size = "w92" if "w92" in sizes else sizes[0]
        if not isinstance(base_url, string_types) or not base_url.startswith("https://"):
            raise ValueError()
        results = _tmdb_json("search/movie", {"query": input})["results"]
        infos = []
        for item in results:
            title = item["title"]
            if item.get("release_date"):
                title = "%s (%s)" % (title, arrow.get(item["release_date"]).year)
            result = {"label": title, "value": item["id"], "title": item["title"]}
            if item.get("poster_path"):
                result["poster"] = base_url + poster_size + item["poster_path"]
                infos.append(result)
        return infos
    except (ValueError, TypeError, KeyError, IndexError):
        raise TmdbUnavailable("TMDB metadata response is unavailable or malformed.")


def tmdbid_to_imdbid(tmdbid):
    try:
        identifier = str(tmdbid)
        if not identifier.isdigit():
            return None, None
        response = _tmdb_json("movie/" + identifier)
        imdbid, title = response["imdb_id"], response["title"]
        if not isinstance(imdbid, string_types) or not re.match(r"^tt[0-9]+\Z", imdbid):
            return None, None
        return imdbid[2:], title
    except (TmdbUnavailable, ValueError, TypeError, KeyError):
        logger.warning("TMDB ID conversion unavailable")
        return None, None


def imdbid_to_tmdbid(imdbid):
    try:
        identifier = str(imdbid)
        if identifier.startswith("tt"):
            identifier = identifier[2:]
        if not identifier.isdigit():
            return None, None
        response = _tmdb_json("find/tt" + identifier, {"external_source": "imdb_id"})
        results = response["movie_results"]
        if len(results) != 1:
            return None, None
        result = results[0]
        return str(result["id"]), result["title"]
    except (TmdbUnavailable, ValueError, TypeError, KeyError):
        logger.warning("TMDB ID conversion unavailable")
        return None, None


def find_series_ids(input):
    info = webaccess.get("https://api.tvmaze.com/search/shows?q=%s" % input)
    info.raise_for_status()
    results = []
    for result in info.json():
        result = result["show"]
        if result["externals"]["thetvdb"] is None:
            logger.info("Did not find TVDB ID for %s. Will skip this result." % result["name"])
            continue
        info = {"label": result["name"], "value": str(result["externals"]["thetvdb"]), "title": result["name"]}
        try:
            info["poster"] = result["image"]["medium"]
        except:
            logger.debug("No poster found for %s" % result["name"])
            pass
        results.append(info)
    return results


def title_from_id(identifier_key, identifier_value):
    if identifier_key is None or identifier_value is None:
        raise AttributeError("Neither identifier key nor value were supplied")
    try:
        if identifier_key == "imdbid":
            if identifier_value[0:2] != "tt":
                identifier_value = "tt%s" % identifier_value
            url = furl("https://www.omdbapi.com").add({"i": identifier_value, "plot": "short", "r": "json"}).tostr()
            omdb = webaccess.get(url)
            return omdb.json()["Title"]

        if identifier_key not in ("rid", "tvdbid"):
            raise AttributeError("Unknown identifier %s" % identifier_key)

        tvmaze_key = "tvrage" if identifier_key == "rid" else "thetvdb"
        tvmaze = webaccess.get(furl("https://api.tvmaze.com/lookup/shows").add({tvmaze_key: identifier_value}).url)
        if tvmaze.status_code == 404:
            #Unfortunately TVMaze returns a 404 for unknown/invalid IDs
            raise ExternalApiInfoException("Unable to find id %s and value %s at TVMaze" % (identifier_key, identifier_value))
        tvmaze.raise_for_status()
        
        return tvmaze.json()["name"]

    except (HTTPError, ConnectionError, ReadTimeout) as e:
        logger.exception("Unable to retrieve title by id %s and value %s" % (identifier_key, identifier_value))
        raise ExternalApiInfoException(str(e))
    except Exception as e:
        logger.exception("Unable to retrieve title by id %s and value %s" % (identifier_key, identifier_value))
        raise ExternalApiInfoException(str(e))


def canConvertId(fromType, toType):
    fromType = fromType.replace("rid", "tvrage").replace("id", "")
    toType = toType.replace("rid", "tvrage").replace("id", "")
    conversionMap = {"imdb": ["tmdb"],
                     "tmdb": ["imdb"],
                     "tvrage": ["tvdb", "tvmaze"],
                     "tvdb": ["tvrage", "tvmaze"],
                     "tvmaze": ["tvdb", "tvrage"]
                     }
    return toType == "title" or (fromType in conversionMap.keys() and toType in conversionMap[fromType])


def canConvertList(fromId, toIdList):
    return any([canConvertId(fromId, x) for x in toIdList])


def _tryFromCache(fromType, toType, id):
    #Return a tuple of a boolean which indicates if a cache entry was found and the cache entry or None
    #This way we will know if a cache entry exists or the cached value is None 
    try:
        if fromType == "tvrage":
            cacheEntry = TvIdCache.get(TvIdCache.tvrage == id)
        elif fromType == "tvdb":
            cacheEntry = TvIdCache.get(TvIdCache.tvdb == id)
        elif fromType == "tvmaze":
            cacheEntry = TvIdCache.get(TvIdCache.tvmaze == id)
        elif fromType == "imdb":
            cacheEntry = MovieIdCache.get(MovieIdCache.imdb == id)
        elif fromType == "tmdb":
            cacheEntry = MovieIdCache.get(MovieIdCache.tmdb == id)
        else:
            return False, None
    except (TvIdCache.DoesNotExist, MovieIdCache.DoesNotExist):
        return False, None
    return True, cacheEntry
        


def _cacheTvMazeIds(tvMaze):
    try:
        cacheEntry = TvIdCache(tvmaze=tvMaze.tvmazeid, tvrage=tvMaze.rageid, tvdb=tvMaze.tvdbid, title=tvMaze.title)
        cacheEntry.save()
        return cacheEntry
    except IntegrityError as e:
        logger.debug("Unable to save cached TvMaze entry to database. Probably already exists")
        pass
    except Exception:
        logger.exception("Unable to save cached TvMaze entry to database")
        pass


def convertId(fromType, toType, id):
    logger.info("Converting from %s value %s to %s " % (fromType, id, toType))
    #Clean up names
    fromType = fromType.replace("rid", "tvrage").replace("id", "")
    toType = toType.replace("rid", "tvrage").replace("id", "")
    if fromType.replace("rid", "tvrage").replace("id", "") == toType.replace("rid", "tvrage").replace("id", ""):
        return id
    
    if toType != "title" and not canConvertId(fromType, toType):
        logger.error("Unable to convert from %s to %s" % (fromType, toType))
        return None
    
    hasCacheEntry, result = _tryFromCache(fromType, toType, id)
    if hasCacheEntry:
        logger.debug("Found conversion from %s value %s to %s in cache" % (fromType, id, toType))
    
    elif fromType == "imdb":
        convertedId, title = imdbid_to_tmdbid(id)
        if convertedId is None:
            return None
        result = MovieIdCache(tmdb=convertedId, imdb=id, title=title) 
        result.save()
        
    elif fromType == "tmdb":
        convertedId, title = tmdbid_to_imdbid(id)
        if convertedId is None:
            return None
        result = MovieIdCache(imdb=convertedId, tmdb=id, title=title)
        result.save()
    
    elif fromType in ("tvrage", "tvdb", "tvmaze"):
        fromType = fromType.replace("tvdb", "thetvdb") #TVMaze uses "thetvdb"...
        result = TvMaze.byId(fromType, id)
        if result is None:
            return None
        result = _cacheTvMazeIds(result)

    if result is None:
        return None
    wantedType = getattr(result, toType)
    if wantedType is None:
        return None
    
    logger.info("Successfully converted from %s value %s to %s " % (fromType, id, toType))
    if isinstance(wantedType, int):
        return str(wantedType)
    return wantedType
    

def convertIdToAny(fromType, possibleToTypes, id):
    """
    Attempts to convert from a given ID to any of the possible IDs
    :param fromType: The ID which we know
    :param possibleToTypes: A list of IDs we would want
    :param id: The ID
    :return: Tuple: True or False for result, type of the converted id, the converted id
    """
    if not isinstance(possibleToTypes, list):
        possibleToTypes = [possibleToTypes]
    fromType = fromType.replace("rid", "tvrage").replace("id", "")
    possibleToTypes = [x.replace("rid", "tvrage").replace("id", "") for x in possibleToTypes]
    if fromType in possibleToTypes:
        return True, fromType, id
    for possibleToType in possibleToTypes:
        if canConvertId(fromType, possibleToType):
            result = convertId(fromType, possibleToType, id)
            return True if result is not None else False, possibleToType, result 
    else:
        logger.info("Unable to convert from ID type %s to any of %s" % (fromType, ",".join(possibleToTypes)))
        return False, None, None
    
    
    
    