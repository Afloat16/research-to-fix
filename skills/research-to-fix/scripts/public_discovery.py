#!/usr/bin/env python3
"""Opt-in, bounded public metadata discovery. Never fetch or execute result URLs."""
import http.client
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

MAX_REQUESTS = 8
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 10
MAX_PER_QUERY = 10
USER_AGENT = "Research-to-Fix/1.0 (+https://github.com/Afloat16/research-to-fix)"
API = {
    "github_repositories": "https://api.github.com/search/repositories",
    "github_issues": "https://api.github.com/search/issues",
    "github_prs": "https://api.github.com/search/issues",
    "crossref": "https://api.crossref.org/works",
    "arxiv": "https://export.arxiv.org/api/query",
    "huggingface_models": "https://huggingface.co/api/models",
    "huggingface_datasets": "https://huggingface.co/api/datasets",
}
GROUPS = {provider: ("github" if provider.startswith("github_") else
                    "huggingface" if provider.startswith("huggingface_") else provider)
          for provider in API}
# A single arXiv request per invocation avoids concurrent or rapid polling.
GROUP_LIMITS = {"github": 4, "crossref": 2, "arxiv": 1, "huggingface": 2}
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
        terms = list(dict.fromkeys(word for word in re.findall(r"[\w.-]+", native)
                                  if word.casefold() not in w.GENERIC and len(word) > 1))[:5]
        if not terms:
            raise ProviderError("invalid_response")
        params = {"search_query": " AND ".join('all:"' + term + '"' for term in terms),
                  "start": 0, "max_results": limit, "sortBy": "relevance", "sortOrder": "descending"}
    else:
        params = {"search": native, "limit": limit}
    return API[provider] + "?" + urllib.parse.urlencode(params)


def request_metadata(url, provider):
    # The only caller constructs this URL from an allowlisted endpoint. Reject
    # redirects, avoid environment proxy credentials, and send no cookies/auth.
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
    raise ProviderError("unavailable")


def discover(plan, approve_public=False, max_requests=6, per_query=8, query_ids=None, transport=request_metadata):
    # Validate and refuse before making a single outbound request.
    if approve_public is not True:
        w.fail("explicit_public_approval_required")
    plan = w.validate_plan(plan)
    w.integer(max_requests, 1, MAX_REQUESTS)
    w.integer(per_query, 1, MAX_PER_QUERY)
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
    for query in query_list:
        provider = query["provider"]
        if provider not in API:
            host_pending.append(query["id"])
            continue
        group = GROUPS[provider]
        record = {"query_id": query["id"], "provider": provider, "returned": 0}
        if group in stopped:
            searches.append(dict(record, status="skipped_budget", reason="provider_stopped_after_" + stopped[group]))
            continue
        if requests >= max_requests or provider_counts.get(group, 0) >= GROUP_LIMITS[group]:
            searches.append(dict(record, status="skipped_budget", reason="request_or_provider_limit"))
            continue
        record["searched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        requests += 1
        provider_counts[group] = provider_counts.get(group, 0) + 1
        try:
            url = make_request(query, per_query)
            found, partial = parse_response(query, transport(url, provider), per_query)
            results.extend(found)
            searches.append(dict(record, status="partial" if partial else "completed", returned=len(found),
                                 reason="provider_incomplete_results" if partial else "metadata_only"))
        except ProviderError as error:
            searches.append(dict(record, status=error.code, reason=error.code))
            if error.code in ("rate_limited", "access_blocked"):
                stopped[group] = error.code
    return {"schema_version": 1, "scope": "public_metadata_discovery", "plan_sha256": w.plan_digest(plan),
            "notice": DISCOVERY_NOTICE, "requests": requests, "results": results,
            "searches": searches, "host_required_queries": host_pending,
            "unselected_queries": [qid for qid in queries if qid not in {q["id"] for q in query_list}],
            "complete": not host_pending and len(query_list) == len(queries)
                        and all(row["status"] == "completed" for row in searches)}


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--approve-public", action="store_true",
                        help="I have reviewed the public fingerprint and consent to these fixed API queries")
    parser.add_argument("--max-requests", type=int, default=6)
    parser.add_argument("--per-query", type=int, default=8)
    parser.add_argument("--query-id", action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if not args.approve_public:
            w.fail("explicit_public_approval_required")
        if args.output.exists() or args.output.is_symlink():
            w.fail("output_exists")
        report = discover(w.read_json(args.plan), args.approve_public, args.max_requests,
                          args.per_query, args.query_id)
        w.write_json(report, args.output)
        return 0
    except (w.WorkflowError, OSError, ValueError, TypeError, RecursionError) as error:
        code = str(error) if isinstance(error, w.WorkflowError) else "invalid_input_or_file_operation"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
