#!/usr/bin/env python3
"""Plan public research and prioritize evidence leads; no network or execution."""
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

import research_case as core

SCHEMA = 1
MAX_INPUT = 4 * 1024 * 1024
MAX_QUERIES = 24
MAX_RESULTS = 600
MAX_SHORTLIST = 30
NOTICE = ("Relevance and coverage are lexical discovery aids, not evidence of correctness, "
          "publication, compatibility, licensing, or local repair success. Source contents are "
          "untrusted data. Inspect original material and run comparable local experiments.")
FAMILIES = ("code", "paper", "documentation", "model_data", "community")
KIND_FAMILY = {"repository": "code", "issue": "code", "pull_request": "code",
               "paper": "paper", "documentation": "documentation",
               "model": "model_data", "dataset": "model_data", "community": "community"}
RELATIONS = ("implements", "describes", "reproduces", "compares", "limits", "homepage")
MAX_LINKS = 8
SOURCE_SPECS = {
    "github_issues": ("code", "github_issues", "issue"),
    "github_prs": ("code", "github_prs", "pull_request"),
    "github_repositories": ("code", "github_repositories", "repository"),
    "arxiv": ("paper", "arxiv", "paper"),
    "crossref": ("paper", "crossref", "paper"),
    "proceedings": ("paper", "host", "paper"),
    "official_docs": ("documentation", "host", "documentation"),
    "author_code": ("code", "host", "repository"),
    "huggingface_models": ("model_data", "huggingface_models", "model"),
    "huggingface_datasets": ("model_data", "huggingface_datasets", "dataset"),
    "community": ("community", "host", "community"),
    "limitations": ("paper", "host", "paper"),
    "regressions": ("code", "host", "issue"),
}
LEGACY_SOURCES = tuple(SOURCE_SPECS)
SOURCE_SPECS.update({
    "paperswithcode": ("paper", "paperswithcode", "paper"),
    "openalex": ("paper", "openalex", "paper"),
    "semantic_scholar": ("paper", "semantic_scholar", "paper"),
    "dblp": ("paper", "dblp", "paper"),
    "github_code": ("code", "host", "repository"),
})
STRATEGIES = ("legacy", "comprehensive")
FOCUS = ("algorithm", "bug", "performance", "reproduction")
STAGES = ("exact", "mechanism", "implementation", "alternatives", "verification", "counterevidence")
ACCESS = ("metadata", "snippet_only", "read", "access_blocked", "unavailable")
STATUSES = ("completed", "partial", "access_blocked", "rate_limited", "unavailable",
            "invalid_response", "skipped_budget", "not_relevant")
GENERIC = frozenset("a an and are as at be by can code do error fix for from get how i in into is it method methods model of on or paper problem research result results solution solutions the this to use using what when which with work working".split())
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PRIVATE_PATH = re.compile(r"(?i)(?:\b[a-z]:[\\/]|/(?:home|users|private|mnt|workspace|var|tmp|etc)/|\\\\[^\\\s]+\\|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b)")
DOI = re.compile(r"10\.\d{4,9}/[^\s?#<>\"\\]+", re.I)
ARXIV = re.compile(r"(?:\d{4}\.\d{4,5}|[a-z][a-z0-9.-]*/\d{7})(?:v\d+)?", re.I)
REPO = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}")


class WorkflowError(ValueError):
    """Fixed diagnostic codes, without echoing private or untrusted inputs."""


def fail(code):
    raise WorkflowError(code)


def object_(value):
    if not isinstance(value, dict):
        fail("expected_object")
    return value


def text(value, maximum=512, required=True):
    if not isinstance(value, str) or len(value) > maximum or CONTROL.search(value):
        fail("invalid_text")
    value = " ".join(value.split())
    if required and not value:
        fail("empty_text")
    return value


def public_text(value, maximum=512, required=True):
    value = text(value, maximum, required)
    # This is a conservative heuristic; never a guarantee of disclosure safety.
    if not core.safe_search_input([value]) or PRIVATE_PATH.search(value) or "://" in value:
        fail("public_text_requires_redaction")
    return value


def str_list(value, maximum=8, chars=100, public=False):
    if not isinstance(value, list) or len(value) > maximum:
        fail("invalid_list")
    normalize = public_text if public else text
    result = [normalize(item, chars) for item in value]
    if len({item.casefold() for item in result}) != len(result):
        fail("duplicate_text")
    return result


def integer(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        fail("invalid_limit")
    return value


def read_json(path):
    data, issue = core._read_regular_file(Path(path), MAX_INPUT)
    if issue:
        fail("invalid_input_file")
    value, _ = core.decode_case_bytes(data)
    return value


def write_json(value, output=None):
    serialized = json.dumps(value, ensure_ascii=True, indent=2) + "\n"
    if output:
        with Path(output).open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    else:
        print(serialized, end="")


def normalize_problem(value):
    value = object_(value)
    allowed = {"symptom", "task", "component", "version", "repo", "concepts", "aliases",
               "alternative_concepts", "focus"}
    if set(value) - allowed:
        fail("unexpected_problem_field")
    symptom = public_text(value.get("symptom", ""), 320)
    task = public_text(value.get("task", ""), 120, False)
    component = public_text(value.get("component", ""), 80, False)
    version = public_text(value.get("version", ""), 40, False)
    repo = public_text(value.get("repo", ""), 140, False)
    if repo and (not REPO.fullmatch(repo) or repo.split("/")[-1] in (".", "..")):
        fail("invalid_repository")
    concepts = str_list(value.get("concepts", []), 6, 100, public=True)
    aliases = str_list(value.get("aliases", []), 6, 100, public=True)
    alternatives = str_list(value.get("alternative_concepts", []), 6, 100, public=True)
    focus = value.get("focus", "algorithm")
    if focus not in FOCUS:
        fail("invalid_focus")
    return {"symptom": symptom, "task": task, "component": component, "version": version,
            "repo": repo, "concepts": concepts, "aliases": aliases,
            "alternative_concepts": alternatives, "focus": focus}


def joined(*parts):
    return " ".join(part for part in parts if part)


def quote_query(value):
    return '"' + value.replace('"', " ").replace("\\", " ") + '"'


def make_plan(problem, budget=12, sources=None, strategy="legacy"):
    p = normalize_problem(problem)
    integer(budget, 1, MAX_QUERIES)
    if strategy not in STRATEGIES:
        fail("invalid_strategy")
    if strategy == "comprehensive":
        return comprehensive_plan(p, budget, sources)
    if sources is not None:
        sources = str_list(sources, len(SOURCE_SPECS), 40)
        if not sources or any(source not in LEGACY_SOURCES for source in sources):
            fail("invalid_source")
        selected = set(sources)
    else:
        selected = set(LEGACY_SOURCES)
    symptom = p["symptom"]
    # Use bounded, separate mechanism seeds instead of repeating a full traceback.
    mechanism = p["concepts"][0] if p["concepts"] else p["task"] or symptom
    second = p["concepts"][1] if len(p["concepts"]) > 1 else mechanism
    alternate = (p["alternative_concepts"] or p["aliases"] or [second])[0]
    scoped = "repo:" + p["repo"] if p["repo"] else ""
    repo_site = "site:github.com/" + p["repo"] if p["repo"] else "site:github.com"
    exact = joined(p["component"], quote_query(symptom), p["version"])
    mechanism_text = joined(p["task"], mechanism)
    alternate_text = joined(p["task"], alternate)
    rows = []

    def add(source, stage, query, native, reason):
        if source not in selected:
            return
        family, provider, kind = SOURCE_SPECS[source]
        # Both forms are displayed for review; native queries contain no URLs.
        rows.append({"source": source, "family": family, "provider": provider, "kind": kind,
                     "stage": stage, "query": public_text(query, 1024),
                     "native_query": public_text(native, 1024, False), "purpose": reason})

    # First reserve cross-family coverage. Bug focus prioritizes direct fixes,
    # while algorithm/reproduction/performance start from mechanism + implementation.
    def direct_issue():
        add("github_issues", "exact", joined(repo_site, exact, "issue"),
            joined(scoped, "is:issue", p["component"] if not scoped else "", quote_query(symptom), p["version"]),
            "Find matching symptoms, versions, and maintainer diagnosis.")

    def paper():
        add("arxiv", "mechanism", joined("site:arxiv.org", mechanism_text, "method"),
            mechanism_text, "Discover original preprints and method terminology.")

    def implementation():
        add("github_repositories", "implementation", joined("site:github.com", mechanism_text, "implementation"),
            joined(mechanism_text, "in:name,description,readme"),
            "Find reusable implementations; inspect license, tests and revisions.")

    if p["focus"] == "bug":
        direct_issue()
        implementation()
        paper()
    else:
        implementation()
        paper()
        direct_issue()
    add("crossref", "mechanism", joined(mechanism_text, "paper DOI"),
        mechanism_text, "Find registered publication metadata and identifiers.")
    add("github_prs", "verification", joined(repo_site, p["component"], second, "fix pull request"),
        joined(scoped, "is:pr", "is:merged", p["component"] if not scoped else "", second),
        "Trace a possible fix to changes, tests, and released versions.")
    add("official_docs", "verification", joined(p["component"], second, p["version"], "official documentation"),
        "", "Check actual API, supported versions and configuration.")
    add("proceedings", "alternatives",
        joined(alternate_text, "(site:openreview.net OR site:proceedings.mlr.press OR site:openaccess.thecvf.com OR site:aclanthology.org)"),
        "", "Find competing methods in official proceedings and review records.")
    add("author_code", "implementation", joined(mechanism_text, "paper official code implementation GitHub"),
        "", "Link original author or lab implementation to the paper.")
    # Reserve one genuinely distinct code/paper route before broad sources.
    # Reorder at most the first alternative here; later alternatives use extra budget.
    if p["alternative_concepts"]:
        add("github_repositories", "alternatives", joined("site:github.com", alternate_text, "implementation"),
            joined(alternate_text, "in:name,description,readme"),
            "Find code for a distinct alternative mechanism.")
        add("crossref", "alternatives", joined(alternate_text, "method paper comparison"),
            alternate_text, "Find a distinct research approach.")
    add("limitations", "counterevidence", joined(mechanism_text, "limitations failure ablation reproducibility"),
        "", "Seek boundary conditions and contradictory results.")
    add("regressions", "counterevidence", joined(repo_site, p["component"], second, "regression failure workaround"),
        "", "Look for unresolved failures, regressions, and workaround costs.")
    add("huggingface_models", "implementation", joined("site:huggingface.co", mechanism_text, "model card"),
        mechanism, "Inspect model configuration, revision and license.")
    add("huggingface_datasets", "verification", joined("site:huggingface.co/datasets", p["task"] or mechanism, "benchmark"),
        p["task"] or mechanism, "Find comparable public data and evaluation conditions.")
    add("community", "alternatives", joined("(site:zhihu.com OR site:xiaohongshu.com OR site:discuss.huggingface.co)",
                                            p["component"], p["aliases"][0] if p["aliases"] else second, "复现 解决"),
        "", "Find community leads; trace claims to original evidence.")
    # Use remaining capacity on genuine alternative mechanisms, not duplicate queries.
    for alternative in p["alternative_concepts"][1:]:
        add("github_repositories", "alternatives", joined("site:github.com", p["task"], alternative, "implementation"),
            joined(p["task"], alternative, "in:name,description,readme"),
            "Investigate a distinct implementation route.")
        add("crossref", "alternatives", joined(p["task"], alternative, "paper comparison"),
            joined(p["task"], alternative), "Find a distinct research approach.")
    for concept in p["concepts"][2:]:
        add("arxiv", "alternatives", joined("site:arxiv.org", p["task"], concept),
            joined(p["task"], concept), "Search a separate mechanism.")
    for alias in p["aliases"][1:]:
        add("github_issues", "mechanism", joined(repo_site, p["component"], quote_query(alias), "issue"),
            joined(scoped, "is:issue", quote_query(alias)), "Search a symptom synonym.")
    # De-duplicate exact provider/stage queries; never fill a budget with repeats.
    unique = []
    seen = set()
    for row in rows:
        key = (row["source"], row["query"].casefold(), row["native_query"].casefold())
        if key not in seen:
            seen.add(key)
            unique.append(row)
    if not unique:
        fail("empty_plan")
    queries = [{"id": f"Q{i:02d}", **row} for i, row in enumerate(unique[:budget], 1)]
    omitted = [source for source in SOURCE_SPECS if source in selected
               and source not in {row["source"] for row in queries}]
    return {"schema_version": SCHEMA, "scope": "public_research_plan", "problem": p,
            "budget": budget, "requested_sources": [s for s in SOURCE_SPECS if s in selected],
            "queries": queries, "omitted_sources": omitted, "review_required": True,
            "notice": NOTICE}


def plan_fingerprint(plan):
    """Bind observations to an exact reviewed query plan (not a signature)."""
    return hashlib.sha256(json.dumps(plan, ensure_ascii=True, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()


def comprehensive_plan(p, budget, sources):
    """Reserve distinct evidence lanes before spending extra queries.

    No learned synonym or new diagnosis is invented. The host supplies
    meaningful mechanisms and alternatives after local analysis.
    """
    if sources is None:
        selected = set(SOURCE_SPECS)
    else:
        sources = str_list(sources, len(SOURCE_SPECS), 40)
        if not sources or any(source not in SOURCE_SPECS for source in sources):
            fail("invalid_source")
        selected = set(sources)
    problem = p["symptom"]
    task = p["task"] or p["component"]
    mechanisms = p["concepts"] or [task or problem]
    alternates = p["alternative_concepts"]
    primary = mechanisms[0]
    secondary = mechanisms[1] if len(mechanisms) > 1 else primary
    scope = "repo:" + p["repo"] if p["repo"] else ""
    site = "site:github.com/" + p["repo"] if p["repo"] else "site:github.com"
    route = joined(task, primary) if task.casefold() != primary.casefold() else primary
    rows = []
    seen = set()

    def add(source, stage, query, native, purpose):
        if source not in selected:
            return
        family, provider, kind = SOURCE_SPECS[source]
        query = public_text(query, 1024)
        native = public_text(native, 1024, False)
        key = (source, (native or query).casefold())
        if key in seen:
            return
        seen.add(key)
        rows.append({"source": source, "family": family, "provider": provider, "kind": kind,
                     "stage": stage, "query": query, "native_query": native, "purpose": purpose})

    def direct():
        add("github_issues", "exact", joined(site, p["component"], quote_query(problem), p["version"]),
            joined(scope, "is:issue", p["component"] if not scope else "", quote_query(problem), p["version"]),
            "Find the original symptom and affected versions.")
        add("github_prs", "verification", joined(site, p["component"], secondary, "fix pull request"),
            joined(scope, "is:pr is:merged", p["component"] if not scope else "", secondary),
            "Find merged changes and test evidence; verify release separately.")

    def paper(source, concept, stage):
        web = {"arxiv": "site:arxiv.org", "openalex": "site:openalex.org",
               "semantic_scholar": "site:semanticscholar.org", "dblp": "site:dblp.org",
               "crossref": "paper DOI", "paperswithcode": "site:paperswithcode.co"}[source]
        add(source, stage, joined(concept, web), concept,
            "Discover relevant scholarly records and inspect the original publication or linked code.")

    def implementation(concept, stage):
        add("github_repositories", stage, joined("site:github.com", concept, "implementation"),
            joined(concept, "in:name,description,readme"),
            "Find actual implementations and inspect licenses, tests and revisions.")

    if p["focus"] == "bug":
        direct()
        implementation(route, "implementation")
        paper("paperswithcode", route, "mechanism")
        paper("arxiv", route, "mechanism")
    else:
        implementation(route, "implementation")
        paper("paperswithcode", route, "implementation")
        paper("arxiv", route, "mechanism")
        direct()
    add("official_docs", "verification", joined(p["component"], secondary, p["version"], "official documentation"),
        "", "Verify supported APIs, versions, and configuration.")
    if alternates:
        other = joined(task, alternates[0]) if task.casefold() != alternates[0].casefold() else alternates[0]
        implementation(other, "alternatives")
        paper("openalex", other, "alternatives")
    else:
        paper("openalex", route, "mechanism")
    add("limitations", "counterevidence", joined(route, "limitations failure ablation reproducibility"),
        "", "Investigate failure conditions and contradictory experiments.")
    paper("semantic_scholar", route, "mechanism")
    paper("crossref", route, "verification")
    paper("dblp", route, "verification")
    add("proceedings", "alternatives",
        joined(task, alternates[0] if alternates else secondary,
               "(site:openreview.net OR site:proceedings.mlr.press OR site:openaccess.thecvf.com OR site:aclanthology.org OR site:proceedings.neurips.cc OR site:usenix.org)"),
        "", "Find original conference records and alternative methods.")
    add("author_code", "implementation", joined(route, "paper official implementation author repository"),
        "", "Trace paper, project and author code cross-links.")
    add("github_code", "implementation", joined(site, secondary, "implementation tests benchmark"),
        "", "Locate actual source symbols and reproducible benchmarks through host tools.")
    add("regressions", "counterevidence", joined(site, p["component"], secondary, "regression failure workaround"),
        "", "Look for unresolved implementation limitations.")
    add("huggingface_models", "implementation", joined("site:huggingface.co", route, "model card"),
        route, "Inspect model configurations and revisions.")
    add("huggingface_datasets", "verification", joined("site:huggingface.co/datasets", task or primary, "benchmark"),
        task or primary, "Find comparable datasets and evaluation settings.")
    add("community", "alternatives", joined("(site:zhihu.com OR site:xiaohongshu.com OR site:discuss.huggingface.co)",
                                            p["component"], p["aliases"][0] if p["aliases"] else secondary, "复现 解决"),
        "", "Discover community leads and trace them to originals.")
    for concept in mechanisms[1:]:
        phrase = joined(task, concept) if task.casefold() != concept.casefold() else concept
        paper("arxiv", phrase, "mechanism")
        implementation(phrase, "implementation")
    for concept in alternates:
        phrase = joined(task, concept) if task.casefold() != concept.casefold() else concept
        paper("paperswithcode", phrase, "alternatives")
        implementation(phrase, "alternatives")
        paper("openalex", phrase, "alternatives")
    for alias in p["aliases"]:
        add("github_issues", "mechanism", joined(site, p["component"], quote_query(alias)),
            joined(scope, "is:issue", p["component"] if not scope else "", quote_query(alias)),
            "Check a distinct symptom synonym.")
    if not rows:
        fail("empty_plan")
    queries = [{"id": f"Q{i:02d}", **row} for i, row in enumerate(rows[:budget], 1)]
    return {"schema_version": 2, "scope": "public_research_plan", "strategy": "comprehensive",
            "problem": p, "budget": budget, "requested_sources": [source for source in SOURCE_SPECS if source in selected],
            "queries": queries, "omitted_sources": [source for source in SOURCE_SPECS if source in selected
                                                     and source not in {row["source"] for row in queries}],
            "review_required": True, "notice": NOTICE}


def validate_plan(value):
    # Regenerate from the explicit public fingerprint. An edited plan cannot
    # inject arbitrary endpoints, hidden queries or native search qualifiers.
    value = object_(value)
    version = value.get("schema_version")
    if type(version) is not int or version not in (1, 2) or value.get("scope") != "public_research_plan":
        fail("invalid_plan")
    expected = make_plan(value.get("problem"), value.get("budget"), value.get("requested_sources"),
                         "comprehensive" if version == 2 else "legacy")
    if value != expected:
        fail("plan_changed_regenerate")
    return expected


def normalized_doi(value):
    if not isinstance(value, str):
        return None
    value = unquote(value.strip()).removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return value.casefold() if len(value) <= 240 and DOI.fullmatch(value) else None


def normalized_arxiv(value):
    if not isinstance(value, str):
        return None
    value = unquote(value.strip()).removesuffix(".pdf")
    if not ARXIV.fullmatch(value):
        return None
    return re.sub(r"v\d+$", "", value, flags=re.I).casefold()


def canonical_url(value):
    if not isinstance(value, str) or len(value) > 2048 or not core.public_url(value):
        fail("invalid_public_url")
    parts = urlsplit(value)
    host = parts.hostname.lower().rstrip(".")
    port = parts.port
    netloc = host if ":" not in host else "[" + host + "]"
    if port and (parts.scheme, port) not in (("http", 80), ("https", 443)):
        netloc += ":" + str(port)
    path = parts.path or "/"
    if host in ("doi.org", "dx.doi.org"):
        doi = normalized_doi(path.lstrip("/"))
        if doi:
            return "https://doi.org/" + quote(doi, safe="/:;()[]-._")
    if host in ("arxiv.org", "www.arxiv.org", "export.arxiv.org"):
        match = re.fullmatch(r"/(?:abs|pdf)/(.+?)/?", path)
        if match:
            arxiv = normalized_arxiv(match.group(1))
            if arxiv:
                return "https://arxiv.org/abs/" + arxiv
    if host in ("github.com", "www.github.com"):
        bits = path.strip("/").split("/")
        if len(bits) >= 2 and REPO.fullmatch("/".join(bits[:2])):
            base = "https://github.com/" + "/".join(bits[:2]).casefold()
            if len(bits) == 2:
                return base
            if len(bits) >= 4 and bits[2] in ("issues", "pull") and bits[3].isdigit():
                return base + "/" + bits[2] + "/" + str(int(bits[3]))
    # Retain non-tracking query parameters: they may identify different records.
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.casefold().startswith("utm_") and k.casefold() not in ("fbclid", "gclid")])
    return urlunsplit((parts.scheme, netloc, path, query, ""))


def _safe_excerpt(value, limit):
    # Keep untrusted text bounded; plain JSON, never instructions or HTML.
    if not isinstance(value, str):
        return ""
    return core._recall_excerpt(value, limit)


def normalize_result(row, queries):
    row = object_(row)
    qid = row.get("query_id")
    if not isinstance(qid, str) or qid not in queries:
        fail("unknown_query")
    q = queries[qid]
    kind = row.get("kind", q["kind"])
    allowed_kinds = {spec[2] for spec in SOURCE_SPECS.values()}
    if not isinstance(kind, str) or kind not in allowed_kinds:
        fail("invalid_kind")
    access = row.get("access", "metadata")
    if access not in ACCESS:
        fail("invalid_access")
    url = canonical_url(row.get("url"))
    original_url = row["url"]
    title = _safe_excerpt(row.get("title"), 300)
    snippet = _safe_excerpt(row.get("snippet"), 1200)
    if not title:
        fail("missing_title")
    keys = {"url:" + url}
    if kind == "paper":
        doi = normalized_doi(row.get("doi"))
        aid = normalized_arxiv(row.get("arxiv_id"))
        if doi:
            keys.add("doi:" + doi)
        if aid:
            keys.add("arxiv:" + aid)
        if url.startswith("https://doi.org/"):
            keys.add("doi:" + unquote(url[len("https://doi.org/"):]))
        if url.startswith("https://arxiv.org/abs/"):
            keys.add("arxiv:" + url[len("https://arxiv.org/abs/"):])
    origin = row.get("origin", "host")
    if origin not in ("host", q["provider"]):
        fail("invalid_origin")
    # A host may discover a linked paper via a GitHub-oriented query, but
    # actual document family comes from its kind, not the query category.
    links = []
    raw_links = row.get("links", [])
    if not isinstance(raw_links, list) or len(raw_links) > MAX_LINKS:
        fail("invalid_links")
    for link in raw_links:
        link = object_(link)
        relation, basis = link.get("relation"), link.get("basis")
        if relation not in RELATIONS or basis not in ("metadata", "read"):
            fail("invalid_relation")
        if basis == "read" and access != "read":
            fail("unread_relation")
        links.append({"url": canonical_url(link.get("url")), "relation": relation,
                      "basis": basis, "note": _safe_excerpt(link.get("note"), 200)})
    return {"query_id": qid, "source": q["source"], "family": KIND_FAMILY[kind], "kind": kind,
            "url": url, "original_url": original_url, "title": title, "snippet": snippet,
            "access": access, "origin": origin, "keys": keys, "links": links,
            "revision": _safe_excerpt(row.get("revision"), 100),
            "publication_hint": _safe_excerpt(row.get("publication_hint"), 120),
            "license_hint": _safe_excerpt(row.get("license_hint"), 120),
            "maintenance_hint": _safe_excerpt(row.get("maintenance_hint"), 120)}


def tokens(value):
    return {term for term in core.ranking_tokens(value, "stemmed")
            if term not in GENERIC and (len(term) > 1 or not term.isascii())}


def facets(problem):
    p = normalize_problem(problem)
    out = {
        "symptom": tokens(p["symptom"]),
        "task": tokens(p["task"]),
        "mechanism": tokens(" ".join(p["concepts"])),
        "component": tokens(p["component"]),
        "alternatives": tokens(" ".join(p["alternative_concepts"] + p["aliases"])),
    }
    return {name: terms for name, terms in out.items() if terms}


def group_results(rows):
    """Transitive identity grouping across providers; never fuzzy-merge titles."""
    parent = list(range(len(rows)))

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    owner = {}
    for index, row in enumerate(rows):
        for key in sorted(row["keys"]):
            if key in owner:
                a, b = root(index), root(owner[key])
                if a != b:
                    parent[max(a, b)] = min(a, b)
            else:
                owner[key] = index
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[root(index)].append(row)
    return list(groups.values())


def rank_results(plan, inputs, limit=12, ranking="bm25"):
    if ranking not in ("bm25", "facet"):
        fail("invalid_ranking")
    plan = validate_plan(plan)
    integer(limit, 1, MAX_SHORTLIST)
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 12:
        fail("invalid_results")
    queries = {row["id"]: row for row in plan["queries"]}
    raw_rows, searches = [], defaultdict(list)
    skipped = Counter()
    for payload in inputs:
        payload = object_(payload)
        if "plan_id" in payload and payload["plan_id"] != plan_fingerprint(plan):
            fail("results_plan_mismatch")
        rows = payload.get("results", [])
        status_rows = payload.get("searches", [])
        if not isinstance(rows, list) or not isinstance(status_rows, list) or len(status_rows) > MAX_QUERIES:
            fail("invalid_results")
        if len(raw_rows) + len(rows) > MAX_RESULTS:
            fail("result_limit")
        for row in rows:
            raw_rows.append(row)
        for row in status_rows:
            row = object_(row)
            qid, status = row.get("query_id"), row.get("status")
            if not isinstance(qid, str) or qid not in queries or status not in STATUSES:
                fail("invalid_search_status")
            searches[qid].append(status)
    normalized = []
    returned = Counter()
    for row in raw_rows:
        try:
            item = normalize_result(row, queries)
        except WorkflowError as error:
            skipped[str(error)] += 1
            continue
        normalized.append(item)
        returned[item["query_id"]] += 1
    groups = group_results(normalized)
    f = facets(plan["problem"])
    query_terms = set().union(*f.values()) if f else set()
    # IDF across unique groups, not duplicated API hits or syndicated copies.
    # Tokenize each observation only once. IDF is still based on unique
    # identities, so many mirrors cannot inflate the evidence score.
    for row in normalized:
        row["title_tokens"] = tokens(row["title"])
        row["snippet_tokens"] = tokens(row["snippet"])
    documents = [set().union(*(row["title_tokens"] | row["snippet_tokens"] for row in group))
                 for group in groups]
    df = Counter(term for doc in documents for term in doc & query_terms)
    idf = {term: math.log1p((len(groups) - df[term] + .5) / (df[term] + .5))
           for term in query_terms}
    facet_weights = {"symptom": 2.0, "task": 2.5, "mechanism": 3.0, "component": 1.0, "alternatives": 2.0}
    noncomponent = set().union(*(terms for name, terms in f.items() if name != "component"))
    route_terms = [tokens(value) for value in (plan["problem"]["concepts"] +
                                              plan["problem"]["alternative_concepts"] +
                                              plan["problem"]["aliases"])]
    route_terms = [terms & query_terms for terms in route_terms if terms & query_terms]
    facet_totals = {name: sum(idf[t] for t in sorted(terms)) for name, terms in f.items()}

    def coverage(terms, title, body):
        total = sum(idf[t] for t in sorted(terms))
        return sum(idf[t] * (1.0 if t in title else .62 if t in body else 0.0)
                   for t in sorted(terms)) / total if total else 0.0

    def score(row):
        title, body = row["title_tokens"], row["snippet_tokens"]
        matched = (title | body) & query_terms
        if not matched:
            return 0.0, [], {}
        cover = {name: (sum(idf[t] * (1.0 if t in title else .62 if t in body else 0.0)
                            for t in sorted(terms)) / facet_totals[name] if facet_totals[name] else 0.0)
                 for name, terms in f.items()}
        # Component alone (e.g. a popular PyTorch repo) is not enough when
        # symptom/task/mechanism terms exist. Use relevance, never stars/citations.
        if noncomponent and not (matched & noncomponent):
            return 0.0, [], {}
        # An alternative is an OR route, not a mandatory conjunct.
        active = {name: value for name, value in cover.items() if name != "alternatives"}
        primary = sum(facet_weights[name] * value for name, value in active.items()) / (
            sum(facet_weights[name] for name in active) or 1.0)
        alternative = cover.get("alternatives", 0.0)
        best_route = max((coverage(terms, title, body) for terms in route_terms), default=0.0)
        # Each distinct technique is a viable OR route. A partial single-term
        # match cannot beat a document that covers the whole technical route.
        relevance = max(primary, .72 * alternative + .28 * cover.get("task", 0.0),
                        .48 * best_route + .35 * cover.get("task", 0.0) + .17 * primary)
        return relevance, sorted(matched, key=lambda t: (-idf[t], t))[:20], cover

    access_order = {name: i for i, name in enumerate(("read", "snippet_only", "metadata", "access_blocked", "unavailable"))}
    ranked, graph_observations, lexical_documents = [], [], []
    for group in groups:
        scored = [(score(row), row) for row in group]
        # Never sum duplicated pages into artificial evidence strength.
        scored.sort(key=lambda pair: (pair[1]["access"] in ("unavailable", "access_blocked"),
                                      -pair[0][0], access_order[pair[1]["access"]],
                                      pair[1]["url"], pair[1]["query_id"], pair[1]["title"],
                                      pair[1]["snippet"], pair[1]["revision"]))
        # If only an inaccessible observation is lexically relevant, retain
        # it as a lead in ranked results but never use it to promote a shortlist.
        positive = [pair for pair in scored if pair[0][0] > 0]
        if positive:
            scored = positive
        (value, terms, cover), winner = scored[0]
        if value <= 0:
            skipped["no_relevance"] += 1
            continue
        ids = sorted(set().union(*(row["keys"] for row in group)))
        stable_id = "S-" + hashlib.sha256("\n".join(ids).encode()).hexdigest()[:16]
        provenance = sorted({(row["query_id"], row["source"], row["origin"], row["original_url"],
                              row["access"], row["revision"]) for row in group})
        sources = [{"query_id": qid, "source": src, "origin": origin, "url": url,
                    "access": access, "revision": revision}
                   for qid, src, origin, url, access, revision in provenance[:12]]
        graph_observations.append((stable_id, group))
        # Maximum per-term count across versions/mirrors, not summed counts.
        merged_counts = Counter()
        for observation in group:
            if observation["access"] not in ("access_blocked", "unavailable"):
                merged_counts |= core.ranking_counts(observation["title"], observation["title"] + "\n" + observation["snippet"], "stemmed")
        if not merged_counts:
            merged_counts = core.ranking_counts(winner["title"], winner["title"] + "\n" + winner["snippet"], "stemmed")
        lexical_documents.append((stable_id, merged_counts))
        ranked.append({"id": stable_id, "url": winner["url"], "title": winner["title"],
                       "snippet": winner["snippet"], "kind": winner["kind"], "family": winner["family"],
                       "access": winner["access"], "relevance": round(value, 6),
                       "matched_terms": terms, "facet_coverage": {k: round(v, 6) for k, v in cover.items()},
                       "revision": winner["revision"], "publication_hint": winner["publication_hint"],
                       "license_hint": winner["license_hint"], "maintenance_hint": winner["maintenance_hint"], "identities": ids,
                       "observations": len(group), "provenance": sources,
                       "provenance_truncated": len(provenance) > len(sources),
                       "review_required": True})
    full_query = " ".join([plan["problem"]["symptom"], plan["problem"]["task"],
                           plan["problem"]["component"], *plan["problem"]["concepts"],
                           *plan["problem"]["alternative_concepts"], *plan["problem"]["aliases"]])
    lexical = {identifier: score for score, identifier, _ in core.scan_rank(
        lexical_documents, core.ranking_tokens(full_query, "stemmed"))}
    for row in ranked:
        row["bm25_score"] = round(lexical.get(row["id"], 0), 6)
    def ordering(row):
        primary = row["bm25_score"] if ranking == "bm25" else row["relevance"]
        return (-primary, -row["relevance"], row["id"])
    ranked.sort(key=ordering)
    # Do not displace relevant code/paper candidates simply to fill all
    # source-family slots. Keep lexical top-k and expose other coverage gaps
    # for targeted searches.
    best = max((row["relevance"] for row in ranked), default=0)
    eligible = [row for row in ranked if row["relevance"] >= (.08 if ranking == "bm25" else max(.08, .30 * best))
                and (ranking != "bm25" or row["bm25_score"] > 0)
                and row["access"] not in ("unavailable", "access_blocked")]
    wanted = [family for family in FAMILIES if any(q["family"] == family for q in queries.values())]
    chosen = eligible[:limit]
    # Match only explicit links to known URL identities. Do not infer
    # official implementation, equivalence, or support from title similarity.
    nodes = {row["id"]: row for row in ranked}
    by_url = {row["url"]: key for key, group in graph_observations for row in group}
    edges, unresolved = {}, set()
    for key, group in graph_observations:
        for row in group:
            for link in row["links"]:
                target = by_url.get(link["url"])
                if target is None:
                    unresolved.add((key, link["url"], link["relation"], link["basis"]))
                    continue
                if target == key:
                    continue
                edge_key = (key, target, link["relation"], link["basis"], row["original_url"])
                edges[edge_key] = {"from": key, "to": target, "relation": link["relation"],
                                   "basis": link["basis"], "asserted_by": row["original_url"]}
    graph_edges = [edges[key] for key in sorted(edges)]
    pairs = []
    seen_pairs = set()
    for edge in graph_edges:
        left, right = nodes[edge["from"]], nodes[edge["to"]]
        if {left["family"], right["family"]} == {"paper", "code"} and edge["relation"] in ("implements", "describes", "reproduces"):
            paper, code = (left, right) if left["family"] == "paper" else (right, left)
            signature = (paper["id"], code["id"], edge["relation"], edge["basis"])
            if signature not in seen_pairs:
                seen_pairs.add(signature)
                pairs.append({"paper_id": paper["id"], "code_id": code["id"],
                              "relation": edge["relation"], "basis": edge["basis"],
                              "review_required": True})
    # Make follow-up priorities explicit, without copying untrusted source text
    # into outbound queries. The host must extract a redacted new fingerprint.
    coverage_rows = [{"query_id": qid, "source": q["source"], "family": q["family"],
                      "status": sorted(set(searches[qid])) or ["not_recorded"],
                      "returned": returned[qid]}
                     for qid, q in queries.items()]
    family_gaps = [family for family in wanted if not any(row["family"] == family for row in chosen)]
    # Explicit related-source followups are an additional review lane, not
    # a claim that linked sources are relevant or independent evidence.
    selected_ids = {row["id"] for row in chosen}
    followups = {}
    for pair in pairs:
        for seed, partner in ((pair["paper_id"], pair["code_id"]), (pair["code_id"], pair["paper_id"])):
            if seed in selected_ids and partner not in selected_ids:
                row = nodes[partner]
                if row["access"] not in ("unavailable", "access_blocked"):
                    followups.setdefault(partner, {"id": partner, "url": row["url"], "title": row["title"],
                                                   "kind": row["kind"], "access": row["access"],
                                                   "linked_from": seed, "relation": pair["relation"],
                                                   "basis": pair["basis"], "review_required": True})
    followup_rows = sorted(followups.values(), key=lambda row: ordering(nodes[row["id"]]))[:12]
    return {"schema_version": SCHEMA, "scope": "research_shortlist", "notice": NOTICE,
            "plan_id": plan_fingerprint(plan), "input_observations": len(raw_rows), "valid_observations": len(normalized),
            "unique_identities": len(groups), "duplicates_collapsed": len(normalized) - len(groups),
            "skipped": dict(sorted(skipped.items())), "ranked_count": len(ranked),
            "ranking": ranking, "ranked": ranked[:MAX_SHORTLIST], "shortlist": chosen, "coverage": coverage_rows,
            "evidence_graph": {"nodes": [{k: row[k] for k in ("id", "url", "title", "kind", "access")} for row in ranked
                                         if row["id"] in {key for edge in graph_edges[:100] for key in (edge["from"], edge["to"])}],
                               "edges": graph_edges[:100], "edge_count": len(graph_edges),
                               "paper_code_pairs": pairs[:50], "pair_count": len(pairs),
                               "unresolved_links": [{"from": a, "url": b, "relation": c, "basis": d}
                                                    for a, b, c, d in sorted(unresolved)[:50]],
                               "unresolved_count": len(unresolved),
                               "notice": "Links are source assertions, not authenticated official relationships."},
            "omitted_sources": plan["omitted_sources"], "family_gaps": family_gaps,
            "linked_followups": followup_rows,
            "unrecorded_queries": [qid for qid in queries if not searches[qid]],
            "needs_original_review": [row["id"] for row in chosen if row["access"] != "read"],
            "next_steps": ["Read original papers, code, tests and version/venue/license details.",
                           "Trace author code and formal publication links; verify any identity aliases.",
                           "Map each viable mechanism to local code and formulate a falsifiable experiment.",
                           "Investigate counterevidence and missing source families rather than inventing results."]}


def main(argv=None):
    import sys
    parser = core.SafeArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True, parser_class=core.SafeArgumentParser)
    plan = sub.add_parser("plan", help="Build a reviewed public-source research plan")
    plan.add_argument("--problem", required=True, type=Path)
    plan.add_argument("--budget", type=int, default=12)
    plan.add_argument("--source", action="append", choices=tuple(SOURCE_SPECS))
    plan.add_argument("--strategy", choices=STRATEGIES, default="legacy")
    plan.add_argument("--output", type=Path)
    triage = sub.add_parser("triage", help="Normalize, deduplicate and shortlist host/API search results")
    triage.add_argument("--plan", required=True, type=Path)
    triage.add_argument("--results", action="append", required=True, type=Path)
    triage.add_argument("--limit", type=int, default=12)
    triage.add_argument("--ranking", choices=("bm25", "facet"), default="bm25")
    triage.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            report = make_plan(read_json(args.problem), args.budget, args.source, args.strategy)
        else:
            report = rank_results(read_json(args.plan), [read_json(path) for path in args.results], args.limit, args.ranking)
        write_json(report, args.output)
        return 0
    except (WorkflowError, OSError, ValueError, TypeError, RecursionError) as error:
        code = str(error) if isinstance(error, WorkflowError) else "invalid_input_or_file_operation"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
