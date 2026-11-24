#!/usr/bin/env python3
"""Opt-in, bounded public metadata discovery. Never fetch or execute result URLs."""
import http.client
from concurrent.futures import ThreadPoolExecutor
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import research_workflow as w
import research_case as core

MAX_REQUESTS = 12
MAX_WORKERS = 4
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 10
MAX_PER_QUERY = 10
MAX_PAPER_LOOKUPS = 4
PAPER_DETAIL = "https://paperswithcode.co/api/v1/papers/arxiv/"
USER_AGENT = "Research-to-Fix/1.0 (+https://github.com/Afloat16/research-to-fix)"
API = {
    "github_repositories": "https://api.github.com/search/repositories",
    "github_issues": "https://api.github.com/search/issues",
    "github_prs": "https://api.github.com/search/issues",
    "crossref": "https://api.crossref.org/works",
    "arxiv": "https://export.arxiv.org/api/query",
    "huggingface_models": "https://huggingface.co/api/models",
    "huggingface_datasets": "https://huggingface.co/api/datasets",
    "paperswithcode": "https://paperswithcode.co/api/v1/papers/",
    "openalex": "https://api.openalex.org/works",
    "semantic_scholar": "https://api.semanticscholar.org/graph/v1/paper/search",
    "dblp": "https://dblp.org/search/publ/api",
}
GROUPS = {provider: ("github" if provider.startswith("github_") else
                    "huggingface" if provider.startswith("huggingface_") else provider)
          for provider in API}
# A single arXiv request per invocation avoids concurrent or rapid polling.
GROUP_LIMITS = {"github": 4, "crossref": 2, "arxiv": 1, "huggingface": 2,
                "paperswithcode": 2, "openalex": 2, "semantic_scholar": 1, "dblp": 1}
DISCOVERY_NOTICE = ("Only the explicitly approved public fingerprint queries are transmitted to fixed public APIs. "
                    "No credentials, private repo contents, result URL fetches, downloads, code execution, or auto-retries. "
                    "Metadata and excerpts are leads, not read/verified original evidence. Host search is needed for other sources.")


class ProviderError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("access_blocked")


def make_request(query, limit):
    provider = query["provider"]
    native = query["native_query"]
    if provider not in API or not native:
        raise ProviderError("unavailable")
    if provider.startswith("github_"):
        params = {"q": native, "per_page": limit}
    elif provider == "crossref":
        params = {"query.bibliographic": native, "rows": limit,
                  "select": "DOI,title,type,published,container-title,relation"}
    elif provider == "arxiv":
        # Prefer a short title/abstract query. In comprehensive mode a broad
        # mechanism query must not require every word of a long symptom.
        terms = list(dict.fromkeys(word.casefold() for word in re.findall(r"[\w.-]+", native)
                                  if word.casefold() not in w.GENERIC and len(word) > 1))[:4]
        if not terms:
            raise ProviderError("invalid_response")
        params = {"search_query": " AND ".join('(ti:"' + term + '" OR abs:"' + term + '")' for term in terms),
                  "start": 0, "max_results": limit, "sortBy": "relevance", "sortOrder": "descending"}
    elif provider == "paperswithcode":
        # Public catalog list includes the paper/repository relation. The
        # public keyword-search endpoint returns summaries without repo URLs.
        # Local reranking is required; date order is not scientific relevance.
        params = {"search": native[:300], "page_size": limit, "include_resources": "true",
                  "has_code": "true", "order_by": "date_published", "order_dir": "desc"}
    elif provider == "openalex":
        params = {"search": native[:300], "per_page": limit,
                  "select": "id,doi,title,publication_year,type,is_retracted,primary_location,abstract_inverted_index"}
    elif provider == "semantic_scholar":
        params = {"query": native[:300].replace("-", " "), "limit": limit,
                  "fields": "paperId,title,abstract,year,venue,externalIds,url,publicationTypes"}
    elif provider == "dblp":
        params = {"q": native[:300], "h": limit, "c": 0, "format": "json"}
    else:
        params = {"search": native, "limit": limit}
    return API[provider] + "?" + urllib.parse.urlencode(params)


def request_metadata(url, provider):
    # The only caller constructs this URL from an allowlisted endpoint. Reject
    # redirects, avoid environment proxy credentials, and send no cookies/auth.
    if provider == "paperswithcode_detail":
        parsed = urllib.parse.urlsplit(url)
        # The exact identifier path is the only non-search request allowed.
        if (parsed.scheme != "https" or parsed.netloc != "paperswithcode.co"
                or not parsed.path.startswith("/api/v1/papers/arxiv/")
                or not w.normalized_arxiv(urllib.parse.unquote(parsed.path.removeprefix("/api/v1/papers/arxiv/")))
                or parsed.query != "include_resources=true" or parsed.fragment):
            raise ProviderError("unavailable")
    else:
        endpoint = API.get(provider)
        if not endpoint or not url.startswith(endpoint + "?"):
            raise ProviderError("unavailable")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    headers = {"User-Agent": USER_AGENT,
               "Accept": "application/atom+xml" if provider == "arxiv" else "application/json"}
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        started = time.monotonic()
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.geturl() != url:
                raise ProviderError("access_blocked")
            blocks, size = [], 0
            while True:
                if time.monotonic() - started > TIMEOUT_SECONDS:
                    raise ProviderError("unavailable")
                block = response.read(min(65536, MAX_RESPONSE_BYTES + 1 - size))
                if not block:
                    break
                size += len(block)
                if size > MAX_RESPONSE_BYTES:
                    raise ProviderError("invalid_response")
                blocks.append(block)
            return b"".join(blocks)
    except urllib.error.HTTPError as error:
        if error.code == 429 or (error.code == 403 and error.headers and
                                 error.headers.get("X-RateLimit-Remaining") == "0"):
            raise ProviderError("rate_limited") from None
        if error.code in (401, 403, 451) or 300 <= error.code < 400:
            raise ProviderError("access_blocked") from None
        raise ProviderError("unavailable") from None
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, http.client.HTTPException):
        raise ProviderError("unavailable") from None


def excerpt(value, limit):
    value = w._safe_excerpt(value, limit)
    # Public APIs sometimes return credential-like strings in issue bodies.
    # Avoid retaining detected values; metadata still requires human review.
    return value if core.safe_search_input([value]) and not w.PRIVATE_PATH.search(value) else ""


def base_row(query, url, title, snippet="", **extra):
    row = {"query_id": query["id"], "origin": query["provider"], "kind": query["kind"],
           "url": url, "title": excerpt(title, 300), "snippet": excerpt(snippet, 700),
           "access": "metadata", **extra}
    try:
        w.normalize_result(row, {query["id"]: query})
    except w.WorkflowError:
        return None
    return row


def parse_github(query, payload, limit):
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ProviderError("invalid_response")
    results = []
    for item in payload["items"][:limit]:
        if not isinstance(item, dict):
            continue
        if query["provider"] == "github_repositories":
            if item.get("private") is not False:
                continue
            license_ = item.get("license")
            license_hint = license_.get("spdx_id", "") if isinstance(license_, dict) else ""
            row = base_row(query, item.get("html_url"), item.get("full_name"),
                           item.get("description"), revision=excerpt(item.get("default_branch"), 100),
                           license_hint=excerpt(license_hint, 120),
                           maintenance_hint="archived; historical implementation only" if item.get("archived") is True else "")
        else:
            is_pr = isinstance(item.get("pull_request"), dict)
            if is_pr != (query["provider"] == "github_prs"):
                continue
            row = base_row(query, item.get("html_url"), item.get("title"),
                           item.get("body"), publication_hint="GitHub state: " + excerpt(item.get("state"), 30))
        if row:
            results.append(row)
    return results, bool(payload.get("incomplete_results"))


def parse_crossref(query, payload, limit):
    try:
        items = payload["message"]["items"]
    except (KeyError, TypeError):
        raise ProviderError("invalid_response") from None
    if not isinstance(items, list):
        raise ProviderError("invalid_response")
    results = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        doi = w.normalized_doi(item.get("DOI"))
        titles = item.get("title")
        if not doi or not isinstance(titles, list) or not titles:
            continue
        venue = item.get("container-title")
        venue = venue[0] if isinstance(venue, list) and venue else ""
        kind = excerpt(item.get("type"), 40)
        # Deposited type/venue are not proof of peer review or publication validity.
        row = base_row(query, "https://doi.org/" + urllib.parse.quote(doi, safe="/:;()[]-._"),
                       titles[0], "", doi=doi,
                       publication_hint=excerpt("Crossref type: " + kind + "; venue: " + excerpt(venue, 65), 120))
        if row:
            results.append(row)
    return results, False


ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def parse_arxiv(query, raw, limit):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ProviderError("invalid_response")
    # Only UTF-8 input is accepted; prevents alternate encodings hiding DTDs.
    try:
        root = ET.fromstring(raw.decode("utf-8"))
    except (UnicodeError, ET.ParseError):
        raise ProviderError("invalid_response") from None
    if root.tag != ATOM + "feed":
        raise ProviderError("invalid_response")
    results = []
    entries = root.findall(ATOM + "entry")
    for entry in entries[:limit]:
        url = entry.findtext(ATOM + "id") or ""
        match = re.fullmatch(r"https?://arxiv\.org/abs/(.+)", url)
        if not match or not w.normalized_arxiv(match.group(1)):
            continue
        raw_id = match.group(1)
        doi = w.normalized_doi(entry.findtext(ARXIV_NS + "doi"))
        row = base_row(query, "https://arxiv.org/abs/" + raw_id,
                       entry.findtext(ATOM + "title"), entry.findtext(ATOM + "summary"),
                       arxiv_id=raw_id, doi=doi, revision=raw_id,
                       publication_hint="arXiv preprint metadata; verify publication separately")
        if row:
            results.append(row)
    if entries and not results:
        raise ProviderError("invalid_response")
    return results, False


def parse_hf(query, payload, limit):
    if not isinstance(payload, list):
        raise ProviderError("invalid_response")
    results = []
    for item in payload[:limit]:
        if not isinstance(item, dict) or item.get("private") is True:
            continue
        identifier = item.get("id")
        if not isinstance(identifier, str) or not w.REPO.fullmatch(identifier):
            continue
        tags = item.get("tags")
        tags = tags if isinstance(tags, list) else []
        tags = [tag for tag in tags[:80] if isinstance(tag, str)]
        license_hint = next((tag[8:] for tag in tags if tag.startswith("license:")), "")
        prefix = "https://huggingface.co/datasets/" if query["provider"] == "huggingface_datasets" else "https://huggingface.co/"
        row = base_row(query, prefix + identifier, identifier, " ".join(tags[:12]),
                       revision=excerpt(item.get("sha"), 100),
                       license_hint=excerpt(license_hint, 120),
                       publication_hint="Gated access metadata" if item.get("gated") else "")
        if row:
            results.append(row)
    return results, False


def doi_url(doi):
    return "https://doi.org/" + urllib.parse.quote(doi, safe="/:;()[]-._")


def paper_url(arxiv_id, doi, fallback):
    if w.normalized_arxiv(arxiv_id):
        return "https://arxiv.org/abs/" + arxiv_id.strip()
    if doi:
        return doi_url(doi)
    return fallback


def reconstruct_abstract(inverted):
    """Bounded OpenAlex position map reconstruction, no unbounded allocation."""
    if not isinstance(inverted, dict) or len(inverted) > 4096:
        return ""
    positions = {}
    for term, indices in inverted.items():
        if not isinstance(term, str) or not 1 <= len(term) <= 160 or not isinstance(indices, list):
            return ""
        if len(indices) > 512:
            return ""
        for index in indices:
            if type(index) is not int or index < 0:
                return ""
            if index >= 256:
                continue
            if index in positions and positions[index] != term:
                return ""
            positions[index] = term
    return " ".join(positions[index] for index in sorted(positions))


def github_repo_url(url):
    try:
        value = w.canonical_url(url)
    except w.WorkflowError:
        return None
    if re.fullmatch(r"https://github\.com/[a-z0-9][a-z0-9-]{0,38}/[a-z0-9_.-]{1,100}", value):
        return value
    return None


def parse_paperswithcode(query, payload, limit):
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ProviderError("invalid_response")
    results = []
    for item in payload["results"][:limit]:
        if not isinstance(item, dict):
            continue
        aid = item.get("arxiv_id")
        doi = w.normalized_doi(item.get("doi"))
        url = paper_url(aid, doi, item.get("url_abs") or item.get("source_url"))
        title = item.get("title")
        records = []
        repos = item.get("repositories")
        if isinstance(repos, list):
            # Retain at most three provider-asserted implementation links
            # per paper. Prefer catalog official hints, never star count.
            valid = [(github_repo_url(repo.get("url")), repo) for repo in repos[:100]
                     if isinstance(repo, dict)]
            valid = [(repo_url, repo) for repo_url, repo in valid if repo_url]
            valid.sort(key=lambda pair: (pair[1].get("is_official") is not True, pair[0]))
            seen = set()
            for repo_url, repo in valid:
                if repo_url in seen:
                    continue
                seen.add(repo_url)
                hint = ("Papers with Code catalog: official implementation candidate"
                        if repo.get("is_official") is True else "Papers with Code catalog: linked repository")
                records.append((repo_url, hint))
                if len(records) == 3:
                    break
        paper = base_row(query, url, title, item.get("abstract"),
                         arxiv_id=aid, doi=doi, revision=excerpt(item.get("version"), 60),
                         publication_hint=excerpt("Catalog metadata; " + excerpt(item.get("conference_name"), 80), 120),
                         links=[{"url": repo_url, "relation": "describes", "basis": "metadata",
                                 "note": hint} for repo_url, hint in records])
        if not paper:
            continue
        results.append(paper)
        for repo_url, hint in records:
            # Link to the paper as the assertion source, not a claim that
            # the repository README or license has been read.
            row = base_row(query, repo_url, repo_url.removeprefix("https://github.com/"),
                           excerpt(title, 250), kind="repository",
                           links=[{"url": url, "relation": "implements", "basis": "metadata", "note": hint}],
                           publication_hint=hint)
            if row:
                results.append(row)
    return results, bool(payload.get("results") and not results)


def parse_openalex(query, payload, limit):
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ProviderError("invalid_response")
    results = []
    for item in payload["results"][:limit]:
        if not isinstance(item, dict):
            continue
        doi = w.normalized_doi(item.get("doi"))
        location = item.get("primary_location")
        location = location if isinstance(location, dict) else {}
        source = location.get("source")
        source = source if isinstance(source, dict) else {}
        landing = location.get("landing_page_url")
        aid = None
        if isinstance(landing, str) and re.match(r"https?://(?:www\.)?arxiv\.org/abs/", landing):
            aid = landing.split("/abs/", 1)[-1]
        hint = excerpt("OpenAlex metadata: " + excerpt(source.get("display_name"), 75), 120)
        row = base_row(query, paper_url(aid, doi, landing or item.get("id")),
                       item.get("title"), reconstruct_abstract(item.get("abstract_inverted_index")),
                       arxiv_id=aid, doi=doi, publication_hint=hint,
                       retraction_hint="retracted" if item.get("is_retracted") is True else "",
                       year=item.get("publication_year"))
        if row:
            results.append(row)
    return results, bool(payload["results"] and not results)


def parse_semantic_scholar(query, payload, limit):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ProviderError("invalid_response")
    results = []
    for item in payload["data"][:limit]:
        if not isinstance(item, dict):
            continue
        ids = item.get("externalIds")
        ids = ids if isinstance(ids, dict) else {}
        doi, aid = w.normalized_doi(ids.get("DOI")), ids.get("ArXiv")
        fallback = item.get("url")
        row = base_row(query, paper_url(aid, doi, fallback), item.get("title"), item.get("abstract"),
                       doi=doi, arxiv_id=aid, year=item.get("year"),
                       publication_hint=excerpt("Semantic Scholar metadata: " + excerpt(item.get("venue"), 75), 120))
        if row:
            results.append(row)
    return results, bool(payload["data"] and not results)


def parse_dblp(query, payload, limit):
    try:
        hits = payload["result"]["hits"]
    except (KeyError, TypeError):
        raise ProviderError("invalid_response") from None
    if not isinstance(hits, dict):
        raise ProviderError("invalid_response")
    items = hits.get("hit", [])
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise ProviderError("invalid_response")
    results = []
    for item in items[:limit]:
        info = item.get("info") if isinstance(item, dict) else None
        if not isinstance(info, dict):
            continue
        doi = w.normalized_doi(info.get("doi"))
        year = info.get("year")
        year = int(year) if isinstance(year, str) and re.fullmatch(r"\d{4}", year) else None
        row = base_row(query, doi_url(doi) if doi else info.get("url"),
                       info.get("title"), "", doi=doi, year=year,
                       publication_hint=excerpt("DBLP metadata: " + excerpt(info.get("venue"), 80), 120))
        if row:
            results.append(row)
    return results, bool(items and not results)


def parse_response(query, raw, limit):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderError("invalid_response")
    provider = query["provider"]
    if provider == "arxiv":
        return parse_arxiv(query, raw, limit)
    try:
        payload, _ = core.decode_case_bytes(raw)
    except (ValueError, TypeError, RecursionError):
        raise ProviderError("invalid_response") from None
    if provider.startswith("github_"):
        return parse_github(query, payload, limit)
    if provider == "crossref":
        return parse_crossref(query, payload, limit)
    if provider.startswith("huggingface_"):
        return parse_hf(query, payload, limit)
    parsers = {"paperswithcode": parse_paperswithcode, "openalex": parse_openalex,
               "semantic_scholar": parse_semantic_scholar, "dblp": parse_dblp}
    if provider in parsers:
        return parsers[provider](query, payload, limit)
    raise ProviderError("unavailable")


def discover(plan, approve_public=False, max_requests=6, per_query=8, query_ids=None,
             transport=request_metadata, workers=1):
    # Validate and refuse before making a single outbound request.
    if approve_public is not True:
        w.fail("explicit_public_approval_required")
    plan = w.validate_plan(plan)
    w.integer(max_requests, 1, MAX_REQUESTS)
    w.integer(per_query, 1, MAX_PER_QUERY)
    w.integer(workers, 1, MAX_WORKERS)
    queries = {query["id"]: query for query in plan["queries"]}
    if query_ids is not None:
        selected = w.str_list(query_ids, len(queries), 8)
        if not selected or any(qid not in queries for qid in selected):
            w.fail("unknown_query")
        query_list = [queries[qid] for qid in selected]
    else:
        query_list = list(queries.values())
    requests, results, searches, host_pending = 0, [], [], []
    provider_counts, stopped = {}, {}
    pending = []
    for query in query_list:
        if query["provider"] not in API:
            host_pending.append(query["id"])
        else:
            pending.append(query)
    if plan["schema_version"] == 2:
        # Round-robin provider groups before spending repeat calls on GitHub.
        # Explicit selection still bounds the exact approved query set.
        buckets = {}
        for query in pending:
            buckets.setdefault(GROUPS[query["provider"]], []).append(query)
        pending = [query for i in range(max(map(len, buckets.values()), default=0))
                   for bucket in buckets.values() for query in bucket[i:i+1]]

    def run_one(query):
        provider = query["provider"]
        record = {"query_id": query["id"], "provider": provider, "returned": 0,
                  "searched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        start = time.monotonic()
        try:
            url = make_request(query, per_query)
            found, partial = parse_response(query, transport(url, provider), per_query)
            # Ordinal is provenance, not an authority signal. Catalog order
            # and linked repositories are intentionally excluded from RRF.
            if provider != "paperswithcode":
                found = [dict(row, provider_rank=i) for i, row in enumerate(found, 1)]
            record.update(status="partial" if partial else "completed", returned=len(found),
                          reason="provider_incomplete_results" if partial else "metadata_only")
        except ProviderError as error:
            found = []
            record.update(status=error.code, reason=error.code)
        except (ValueError, TypeError, RecursionError, KeyError, OverflowError):
            found = []
            record.update(status="invalid_response", reason="invalid_response")
        record["elapsed_ms"] = round((time.monotonic() - start) * 1000, 3)
        return found, record

    # One request per group per wave. No simultaneous requests to the same
    # provider, no automatic retries, and deterministic output order.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        while pending:
            wave, rest, wave_groups = [], [], set()
            for query in pending:
                provider = query["provider"]
                group = GROUPS[provider]
                record = {"query_id": query["id"], "provider": provider, "returned": 0}
                if group in stopped:
                    searches.append(dict(record, status="skipped_budget", reason="provider_stopped_after_" + stopped[group]))
                elif requests >= max_requests or provider_counts.get(group, 0) >= GROUP_LIMITS[group]:
                    searches.append(dict(record, status="skipped_budget", reason="request_or_provider_limit"))
                elif len(wave) >= workers or group in wave_groups:
                    rest.append(query)
                else:
                    wave.append(query)
                    wave_groups.add(group)
                    requests += 1
                    provider_counts[group] = provider_counts.get(group, 0) + 1
            pending = rest
            for query, (found, record) in zip(wave, executor.map(run_one, wave)):
                results.extend(found)
                searches.append(record)
                if record["status"] in ("rate_limited", "access_blocked"):
                    stopped[GROUPS[query["provider"]]] = record["status"]
    order = {qid: i for i, qid in enumerate(queries)}
    searches.sort(key=lambda row: order[row["query_id"]])
    results.sort(key=lambda row: order[row["query_id"]])
    return {"schema_version": 1, "scope": "public_metadata_discovery",
            "plan_id": w.plan_fingerprint(plan), "notice": DISCOVERY_NOTICE, "requests": requests,
            "provider_requests": dict(sorted(provider_counts.items())), "workers": workers,
            "results": results, "searches": searches, "host_required_queries": host_pending,
            "unselected_queries": [qid for qid in queries if qid not in {q["id"] for q in query_list}],
            "complete": not host_pending and len(query_list) == len(queries)
                        and all(row["status"] == "completed" for row in searches)}


def paper_detail_request(value):
    # Only explicit, reviewed bibliographic IDs, never result URLs. A
    # versioned ID resolves its work's current catalog record; provenance
    # reports that record's version rather than promising the old version.
    if not isinstance(value, str) or len(value) > 40:
        w.fail("invalid_arxiv_id")
    identifier = w.normalized_arxiv(value)
    if not identifier or not w.ARXIV.fullmatch(value):
        w.fail("invalid_arxiv_id")
    return PAPER_DETAIL + urllib.parse.quote(identifier, safe="") + "?include_resources=true"


def resolve_papers(plan, paper_ids, query_id, approve_public=False, transport=request_metadata):
    if approve_public is not True:
        w.fail("explicit_public_approval_required")
    plan = w.validate_plan(plan)
    if not isinstance(paper_ids, list) or not 1 <= len(paper_ids) <= MAX_PAPER_LOOKUPS:
        w.fail("invalid_paper_lookup_count")
    queries = {row["id"]: row for row in plan["queries"]}
    if not isinstance(query_id, str) or query_id not in queries or queries[query_id]["provider"] != "paperswithcode":
        w.fail("paper_lookup_requires_catalog_query")
    q = queries[query_id]
    # Validate every ID before any outbound request; collapse versions.
    urls = [paper_detail_request(value) for value in paper_ids]
    if len(set(urls)) != len(urls):
        w.fail("duplicate_paper_lookup")
    results, lookups, stopped = [], [], None
    for value, url in zip(paper_ids, urls):
        identity = w.normalized_arxiv(value)
        if stopped:
            lookups.append({"arxiv_id": identity, "status": "skipped_budget",
                            "reason": "provider_stopped_after_" + stopped, "returned": 0})
            continue
        start = time.monotonic()
        row = {"arxiv_id": identity, "status": "unavailable", "returned": 0,
               "searched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        try:
            raw = transport(url, "paperswithcode_detail")
            if not isinstance(raw, bytes) or not raw or len(raw) > MAX_RESPONSE_BYTES:
                raise ProviderError("invalid_response")
            payload, _ = core.decode_case_bytes(raw)
            if not isinstance(payload, dict) or w.normalized_arxiv(payload.get("arxiv_id")) != identity:
                raise ProviderError("invalid_response")
            found, partial = parse_paperswithcode(q, {"results": [payload]}, 1)
            results.extend(found)
            row.update(status="partial" if partial else "completed", returned=len(found))
        except ProviderError as error:
            row["status"] = error.code
            if error.code in ("rate_limited", "access_blocked"):
                stopped = error.code
        except (ValueError, TypeError, RecursionError, KeyError, OverflowError):
            row["status"] = "invalid_response"
        row["elapsed_ms"] = round((time.monotonic() - start) * 1000, 3)
        lookups.append(row)
    statuses = {row["status"] for row in lookups}
    completed = statuses == {"completed"}
    # Lookup is not evidence that the original broad search ran. Keep its
    # status separate and bind results to the reviewed query for triage.
    return {"schema_version": 1, "scope": "public_paper_link_resolution",
            "plan_id": w.plan_fingerprint(plan), "query_id": query_id,
            "notice": DISCOVERY_NOTICE, "lookups": lookups, "results": results, "searches": [],
            "requests": sum("searched_at" in row for row in lookups), "complete": completed}


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--approve-public", action="store_true",
                        help="I have reviewed the public fingerprint and consent to these fixed API queries")
    parser.add_argument("--max-requests", type=int, default=6)
    parser.add_argument("--per-query", type=int, default=8)
    parser.add_argument("--workers", type=int, default=1, help="Independent provider groups only (1–4)")
    parser.add_argument("--query-id", action="append")
    parser.add_argument("--resolve-paper-id", action="append",
                        help="Resolve explicitly reviewed arXiv IDs via the catalog (max 4); requires one catalog query ID")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if not args.approve_public:
            w.fail("explicit_public_approval_required")
        if args.output.exists() or args.output.is_symlink():
            w.fail("output_exists")
        plan = w.read_json(args.plan)
        if args.resolve_paper_id:
            if not args.query_id or len(args.query_id) != 1:
                w.fail("paper_lookup_requires_catalog_query")
            if len(args.resolve_paper_id) > args.max_requests:
                w.fail("invalid_paper_lookup_count")
            report = resolve_papers(plan, args.resolve_paper_id, args.query_id[0], args.approve_public)
        else:
            report = discover(plan, args.approve_public, args.max_requests,
                              args.per_query, args.query_id, workers=args.workers)
        w.write_json(report, args.output)
        return 0
    except (w.WorkflowError, OSError, ValueError, TypeError, RecursionError) as error:
        code = str(error) if isinstance(error, w.WorkflowError) else "invalid_input_or_file_operation"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
