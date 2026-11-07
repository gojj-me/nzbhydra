from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import re
import urlparse

import arrow
from bs4 import BeautifulSoup
from furl import furl
from six import string_types

from nzbhydra import config
from nzbhydra.exceptions import IndexerResultParsingException, IndexerAccessException
from nzbhydra.nzb_search_result import NzbSearchResult
from nzbhydra.search_module import SearchModule, IndexerProcessingResult


class Binsearch(SearchModule):
    # The public frontend uses zero-based pages of 25 collections.
    uses_page_numbers = True
    size_pattern = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?)B$", re.I)
    guid_pattern = re.compile(r"^[A-Za-z0-9_-]+={0,2}\Z")

    def __init__(self, settings):
        super(Binsearch, self).__init__(settings)
        self.module = "Binsearch"
        self.limit = 25
        self.supports_queries = True
        self.needs_queries = True
        self.category_search = False
        # The frontend advertises no remote size/age filters. Shared result
        # acceptance still applies requested size/age restrictions locally.
        self.supportedFilters = []
        self.supportsNot = False

    def build_base_url(self, offset=0):
        f = furl(self.host)
        f.path.add("search")
        f.args["page"] = int(offset // self.limit)
        return f

    def get_search_urls(self, search_request):
        return [self.build_base_url(search_request.offset or 0).add(
            {"q": search_request.query}).tostr()]

    def get_showsearch_urls(self, search_request):
        urls = []
        query = search_request.query
        if search_request.query:
            urls = self.get_search_urls(search_request)
        if search_request.season is not None:
            # Restrict query if  season and/or episode is given. Use s01e01 and 1x01 and s01 and "season 1" formats
            # binsearch doesn't seem to support "or" in searches, so create separate queries
            urls = []
            if search_request.episode is not None:
                if self.isNumber(search_request.episode):
                    search_request.query = "%s s%02de%02d" % (query, int(search_request.season), int(search_request.episode))
                    urls.extend(self.get_search_urls(search_request))
                    search_request.query = "%s %dx%02d" % (query, int(search_request.season), int(search_request.episode))
                    urls.extend(self.get_search_urls(search_request))
                else:
                    search_request.query = '%s "%s %s"' % (search_request.query, str(search_request.season), search_request.episode.replace("/", " "))
                    self.debug("Assuming we're searching for a daily show. Using query: " + search_request.query)
                    urls = self.get_search_urls(search_request)
            elif self.isNumber(search_request.season):
                search_request.query = "%s s%02d" % (query, int(search_request.season))
                urls.extend(self.get_search_urls(search_request))
                search_request.query = '%s "season %d"' % (query, int(search_request.season))
                urls.extend(self.get_search_urls(search_request))
        return urls

    def get_moviesearch_urls(self, search_request):
        return self.get_search_urls(search_request)
    
    def get_ebook_urls(self, search_request):
        if not search_request.query and (search_request.author or search_request.title):
            search_request.query = "%s %s" % (search_request.author if search_request.author else "", search_request.title if search_request.title else "")
        urls = []
        query = search_request.query
        search_request.query = query + " ebook"
        urls.extend(self.get_search_urls(search_request))
        search_request.query = query + " mobi"
        urls.extend(self.get_search_urls(search_request))
        search_request.query = query + " pdf"
        urls.extend(self.get_search_urls(search_request))
        search_request.query = query + " epub"
        urls.extend(self.get_search_urls(search_request))
        return urls

    def get_audiobook_urls(self, search_request):
        return self.get_search_urls(search_request)

    def get_comic_urls(self, search_request):
        return self.get_search_urls(search_request)

    def get_anime_urls(self, search_request):
        return self.get_search_urls(search_request)
    
    def valid_guid(self, guid):
        return isinstance(guid, string_types) and len(guid) <= 128 and bool(self.guid_pattern.match(guid))

    def get_details_link(self, guid):
        if not self.valid_guid(guid):
            raise ValueError("Invalid Binsearch identifier")
        f = furl(self.host)
        f.path.add("details")
        f.path.add(guid)
        return f.tostr()

    def parse_size(self, text):
        match = self.size_pattern.match(text.strip())
        if not match:
            raise ValueError("Missing size")
        return int(float(match.group(1)) * 1024 ** ("", "K", "M", "G", "T").index(match.group(2).upper()))

    def parse_age(self, text):
        text = text.strip().lower()
        if text in ("just now", "now"):
            return arrow.utcnow()
        match = re.match(r"^(?:about )?(\d+) (second|minute|hour|day|week|month|year)s?(?: ago)?$", text)
        if not match:
            raise ValueError("Unsupported relative age")
        count, unit = int(match.group(1)), match.group(2)
        # Relative month/year labels are approximate; use calendar offsets.
        return arrow.utcnow().replace(**{unit + "s": -count})

    def result_metadata(self, guid, title):
        if not self.valid_guid(guid) or not title.strip():
            raise ValueError("Missing collection metadata")
        entry = self.create_nzb_search_result()
        entry.indexerguid, entry.title = guid, self.cleanUpTitle(title.strip())
        entry.link, entry.details_link = self.get_nzb_link(guid, title), self.get_details_link(guid)
        entry.has_nfo = NzbSearchResult.HAS_NFO_NO
        entry.passworded = "password protect" in title.lower() or "passworded" in title.lower()
        return entry

    def parseRow(self, row):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 4:
            raise ValueError("Unsupported result row")
        checkbox = cells[1].find("input", type="checkbox")
        guid = checkbox["name"]
        link = cells[2].find("a", href="/details/" + guid)
        entry = self.result_metadata(guid, link.get_text())
        sizes = [span.get_text().strip() for span in cells[2].find_all("span")
                 if self.size_pattern.match(span.get_text().strip())]
        if len(sizes) != 1:
            raise ValueError("Missing or ambiguous size")
        entry.size = self.parse_size(sizes[0])
        groups = []
        for anchor in cells[2].find_all("a", href=True):
            parsed = urlparse.urlsplit(anchor["href"])
            if parsed.path != "/search":
                continue
            params = urlparse.parse_qs(parsed.query)
            if params.get("poster"):
                entry.poster = params["poster"][0]
            if params.get("group"):
                groups.extend(params["group"])
        entry.group = ", ".join(groups)
        self.getDates(entry, self.parse_age(cells[3].get_text()), False)
        entry.age_precise = False
        return entry

    def collection_form(self, html):
        if not isinstance(html, string_types) or not html.strip():
            raise ValueError("Empty response")
        soup = BeautifulSoup(html, config.settings.searching.htmlParser)
        if soup.title is None or "binsearch" not in soup.title.get_text().lower():
            raise ValueError("Unrecognized page")
        form = soup.find("form", action="/nzb")
        if form is None or form.get("method", "get").lower() != "get":
            raise ValueError("Missing collection form")
        table = form.find("table", class_="result-table")
        if table is None:
            raise ValueError("Missing collection table")
        return soup, form, table

    def process_query_result(self, html, searchRequest, maxResults=None):
        try:
            soup, form, table = self.collection_form(html)
            if form.find("input", attrs={"name": "q"}) is None:
                raise ValueError("Not a search page")
            pager = soup.find(attrs={"aria-label": "Pagination"})
            current = pager.find(attrs={"aria-current": "page"})
            next_page = pager.find(attrs={"aria-label": "Next page"})
            if next_page.get("aria-disabled") not in ("true", "false"):
                raise ValueError("Unknown pagination")
            page = int(current.get_text().strip()) - 1
            if page != int((searchRequest.offset or 0) // self.limit):
                raise ValueError("Provider did not advance to the requested page")
            rows = [row for row in table.find_all("tr") if row.find_all("td", recursive=False)]
            if len(rows) > self.limit:
                raise ValueError("Unsupported page size")
            entries, rejected, identifiers = [], self.getRejectedCountDict(), set()
            for row in rows:
                entry = self.parseRow(row)
                if entry.indexerguid in identifiers:
                    raise ValueError("Duplicate collection identifier")
                identifiers.add(entry.indexerguid)
                accepted, reason, rejection = self.accept_result(entry, searchRequest, self.supportedFilters)
                if accepted:
                    entries.append(entry)
                else:
                    rejected[rejection] += 1
            has_more = bool(rows) and next_page["aria-disabled"] == "false"
            # Report this page count; the search cache accumulates provider pages.
            return IndexerProcessingResult(entries=entries, queries=[], total=len(rows),
                total_known=not has_more, has_more=has_more, rejected=rejected)
        except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError):
            # Never log provider HTML, result text, poster details or query values.
            raise IndexerResultParsingException("Unsupported or malformed Binsearch search response", self)

    def parse_details(self, html, guid):
        soup, form, table = self.collection_form(html)
        if form.find("input", attrs={"name": "id"})["value"] != guid:
            raise ValueError("Mismatched collection")
        title = form.find("input", attrs={"name": "name"})["value"]
        entry = self.result_metadata(guid, title)
        sizes, dates = [], []
        for row in table.find_all("tr"):
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue
            if len(cells) != 3:
                raise ValueError("Unsupported file row")
            size = [span.get_text().strip() for span in cells[1].find_all("span")
                    if self.size_pattern.match(span.get_text().strip())]
            if len(size) != 1:
                raise ValueError("Missing file size")
            sizes.append(self.parse_size(size[0]))
            dates.append(self.parse_age(cells[2].get_text()))
        if not sizes:
            raise ValueError("Missing collection files")
        entry.size = sum(sizes)
        self.getDates(entry, min(dates), False)
        entry.age_precise = False
        return entry

    def get_entry_by_id(self, guid, title):
        if not self.valid_guid(guid):
            return None
        response, access, _ = self.get_url_with_papi_access(self.get_details_link(guid), "details", saveToDb=False)
        if response is None:
            if not getattr(access, "_rate_limit_skipped", False):
                self.saveIndexerStatus(access)
            return None
        try:
            entry = self.parse_details(response.text, guid)
            self.handle_indexer_success()
            return entry
        except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError):
            access.response_successful = False
            access.error = "Binsearch collection metadata is unavailable or malformed"
            self.warn(access.error)
            self.handle_indexer_failure(reason=access.error)
            return None
        finally:
            self.saveIndexerStatus(access)

    def get_nfo(self, guid):
        return False, None, "NFO retrieval is unavailable through the Binsearch integration."

    def get_nzb_link(self, guid, title):
        if not self.valid_guid(guid):
            raise ValueError("Invalid Binsearch identifier")
        f = furl(self.host)
        f.path.add("nzb")
        return f.add({"id": guid}).tostr()

    def check_auth(self, body):
        if "The search service is temporarily unavailable" in body:
            raise IndexerAccessException("The search service is temporarily unavailable.", self)


def get_instance(settings):
    return Binsearch(settings)
