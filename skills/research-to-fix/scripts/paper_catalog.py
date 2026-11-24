#!/usr/bin/env python3
"""Build and query a local, explicit paper-to-code metadata catalog.

The archive/database is not shipped with the skill. Import a reviewed JSONL
file of public metadata (one object per line). Only open catalogs you built
yourself. No network, automatic scanning, code execution or extension loading.
"""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import unicodedata
from time import perf_counter_ns

import public_discovery as discovery
import research_case as core
import research_workflow as w

MAX_BYTES = 512 * 1024 * 1024
MAX_DB_BYTES = 1024 * 1024 * 1024
MAX_LINE = 64 * 1024
MAX_ROWS = 1_000_000
MAX_PAPERS = 20
MAX_LINKS = 3
SCHEMA = 2
NOTICE = ("Local catalog metadata is user-supplied and not independently authenticated. "
          "Historical official flags are leads, not current license, maintenance, applicability or correctness guarantees.")


@lru_cache(maxsize=8192)
def repo_url(value):
    return discovery.github_repo_url(value)


@lru_cache(maxsize=8192)
def paper_identity(arxiv, landing):
    aid = w.normalized_arxiv(arxiv)
    if aid:
        return "arxiv:" + aid, "https://arxiv.org/abs/" + aid
    try:
        url = w.canonical_url(landing)
    except w.WorkflowError:
        return None
    return "url:" + url, url


def title_key(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def normalize(row):
    if not isinstance(row, dict):
        return None
    raw_repo, aid, landing = row.get("repo_url"), row.get("paper_arxiv_id"), row.get("paper_url_abs")
    if not isinstance(raw_repo, str) or len(raw_repo) > 2048:
        return None
    aid = aid if isinstance(aid, str) and len(aid) <= 40 else ""
    landing = landing if isinstance(landing, str) and len(landing) <= 2048 else ""
    repo = repo_url(raw_repo)
    paper = paper_identity(aid, landing)
    title = discovery.excerpt(row.get("paper_title"), 300)
    abstract = discovery.excerpt(row.get("paper_abstract", row.get("abstract")), 1200)
    if not repo or not paper or not title:
        return None
    key, url = paper
    return ((key, url, title, abstract, title_key(title)),
            (key, repo, int(row.get("is_official") is True),
             int(row.get("mentioned_in_paper") is True), int(row.get("mentioned_in_github") is True)))


def stream_rows(path, digest):
    path = Path(path)
    before = path.lstat()
    if not core.plain_stat(before, stat.S_ISREG) or before.st_size > MAX_BYTES:
        w.fail("invalid_catalog_input")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as handle:
        initial = os.fstat(handle.fileno())
        if not core.plain_stat(initial, stat.S_ISREG) or (before.st_dev, before.st_ino) != (initial.st_dev, initial.st_ino):
            w.fail("catalog_input_changed")
        size, count = 0, 0
        while True:
            line = handle.readline(MAX_LINE + 1)
            if not line:
                break
            size += len(line)
            count += 1
            if len(line) > MAX_LINE or size > MAX_BYTES or count > MAX_ROWS:
                w.fail("catalog_input_limit")
            digest.update(line)
            if not line.strip():
                continue
            try:
                value, _ = core.decode_case_bytes(line)
            except (ValueError, TypeError, RecursionError):
                w.fail("invalid_catalog_jsonl")
            yield value
        after = os.fstat(handle.fileno())
        if size != initial.st_size or after.st_size != initial.st_size or after.st_mtime_ns != initial.st_mtime_ns:
            w.fail("catalog_input_changed")


CREATE = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE papers (
    id TEXT PRIMARY KEY, url TEXT NOT NULL, title TEXT NOT NULL, abstract TEXT NOT NULL, title_key TEXT NOT NULL
) WITHOUT ROWID;
CREATE TABLE links (
    paper_id TEXT NOT NULL REFERENCES papers(id), repo_url TEXT NOT NULL,
    official INTEGER NOT NULL, in_paper INTEGER NOT NULL, in_repo INTEGER NOT NULL,
    PRIMARY KEY(paper_id, repo_url)
) WITHOUT ROWID;
CREATE VIRTUAL TABLE paper_fts USING fts5(id UNINDEXED, title, abstract, tokenize='porter unicode61');
"""
PAPER_INSERT = """
INSERT INTO papers VALUES(?,?,?,?,?)
ON CONFLICT(id) DO UPDATE SET
title=CASE WHEN length(excluded.title)>length(papers.title)
             OR (length(excluded.title)=length(papers.title) AND excluded.title<papers.title)
           THEN excluded.title ELSE papers.title END,
title_key=CASE WHEN length(excluded.title)>length(papers.title)
             OR (length(excluded.title)=length(papers.title) AND excluded.title<papers.title)
           THEN excluded.title_key ELSE papers.title_key END,
abstract=CASE WHEN length(excluded.abstract)>length(papers.abstract)
             OR (length(excluded.abstract)=length(papers.abstract) AND excluded.abstract<papers.abstract)
           THEN excluded.abstract ELSE papers.abstract END
"""
LINK_INSERT = """
INSERT INTO links VALUES(?,?,?,?,?)
ON CONFLICT(paper_id,repo_url) DO UPDATE SET
official=max(links.official,excluded.official),
in_paper=max(links.in_paper,excluded.in_paper),
in_repo=max(links.in_repo,excluded.in_repo)
"""


def build_catalog(input_path, database, source="user-supplied metadata", license_="unknown", snapshot="unknown"):
    source, license_, snapshot = (w.text(source, 200), w.text(license_, 100), w.text(snapshot, 100))
    database = Path(database)
    # Never overwrite an existing file or link. Only delete a newly created
    # database on failure; no adjacent or unrelated directories are scanned.
    fd = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600)
    os.close(fd)
    start = perf_counter_ns()
    digest = hashlib.sha256()
    db = None
    counts = Counter()
    try:
        db = sqlite3.connect(database)
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.executescript(CREATE)
        db.execute(f"PRAGMA user_version={SCHEMA}")
        paper_batch, link_batch = [], []

        def flush():
            if paper_batch:
                db.executemany(PAPER_INSERT, paper_batch)
                db.executemany(LINK_INSERT, link_batch)
                paper_batch.clear()
                link_batch.clear()

        for row in stream_rows(input_path, digest):
            counts["rows_seen"] += 1
            item = normalize(row)
            if not item:
                counts["invalid_rows"] += 1
                continue
            counts["accepted_rows"] += 1
            paper, link = item
            paper_batch.append(paper)
            link_batch.append(link)
            if len(paper_batch) >= 2048:
                flush()
        flush()
        if not counts["accepted_rows"]:
            w.fail("empty_catalog")
        db.execute("CREATE INDEX paper_title_key ON papers(title_key,id)")
        db.execute("CREATE INDEX repo_paper_id ON links(repo_url,paper_id)")
        db.execute("INSERT INTO paper_fts(id,title,abstract) SELECT id,title,abstract FROM papers ORDER BY id")
        papers = db.execute("SELECT count(*) FROM papers").fetchone()[0]
        links = db.execute("SELECT count(*) FROM links").fetchone()[0]
        metadata = {"source": source, "license": license_, "snapshot": snapshot,
                    "input_sha256": digest.hexdigest(), "papers": str(papers), "links": str(links)}
        db.executemany("INSERT INTO meta VALUES(?,?)", sorted(metadata.items()))
        db.commit()
        db.close()
        db = None
        if database.stat().st_size > MAX_DB_BYTES:
            w.fail("catalog_database_limit")
        return {"scope": "local_catalog_build", "notice": NOTICE, "source": source,
                "license": license_, "snapshot": snapshot, "input_sha256": digest.hexdigest(),
                "rows_seen": counts["rows_seen"], "invalid_rows": counts["invalid_rows"],
                "accepted_rows": counts["accepted_rows"], "papers": papers, "links": links,
                "database_bytes": database.stat().st_size,
                "build_ms": round((perf_counter_ns() - start) / 1e6, 3),
                "sqlite_version": sqlite3.sqlite_version}
    except BaseException:
        if db is not None:
            db.close()
        database.unlink(missing_ok=True)
        raise


class Catalog:
    """Read only a stable, locally built database; never open an unknown DB."""
    def __init__(self, database):
        path = Path(database)
        info = path.lstat()
        if not core.plain_stat(info, stat.S_ISREG) or info.st_size > MAX_DB_BYTES:
            w.fail("invalid_catalog_database")
        uri = path.resolve(strict=True).as_uri() + "?mode=ro&immutable=1"
        self.db = sqlite3.connect(uri, uri=True)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA trusted_schema=OFF")
            self.db.execute("PRAGMA query_only=ON")
            if self.db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA:
                w.fail("catalog_schema_requires_rebuild")
            self.metadata = dict(self.db.execute("SELECT key,value FROM meta"))
            if set(self.metadata) != {"source", "license", "snapshot", "input_sha256", "papers", "links"}:
                w.fail("invalid_catalog_metadata")
            if not re.fullmatch(r"[0-9a-f]{64}", self.metadata["input_sha256"]):
                w.fail("invalid_catalog_metadata")
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def search(self, query, limit=12):
        w.integer(limit, 1, MAX_PAPERS)
        query = w.public_text(query, 1024)
        terms = list(dict.fromkeys(word.casefold() for word in re.findall(r"[^\W_]+", query)
                                  if len(word) > 1 and word.casefold() not in w.GENERIC))[:32]
        if not terms:
            return []
        expression = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
        return [dict(row) for row in self.db.execute(
            "SELECT id,title,abstract,bm25(paper_fts,0,4,1) AS score FROM paper_fts "
            "WHERE paper_fts MATCH ? ORDER BY score,id LIMIT ?", (expression, limit))]

    def lookup(self, arxiv_id):
        discovery.paper_detail_request(arxiv_id)
        key = "arxiv:" + w.normalized_arxiv(arxiv_id)
        row = self.db.execute("SELECT * FROM papers WHERE id=?", (key,)).fetchone()
        return dict(row) if row else None

    def lookup_title(self, title, limit=12):
        """Exact normalized title lookup. Multiple identities remain distinct."""
        w.integer(limit, 1, MAX_PAPERS)
        title = w.public_text(title, 1024)
        return [dict(row) for row in self.db.execute(
            "SELECT id,url,title,abstract FROM papers WHERE title_key=? ORDER BY id LIMIT ?",
            (title_key(title), limit))]

    def papers_for_repository(self, url, limit=12):
        """Reverse lookup by an explicit reviewed GitHub repository URL."""
        w.integer(limit, 1, MAX_PAPERS)
        if not isinstance(url, str):
            w.fail("invalid_repository_url")
        normalized = discovery.github_repo_url(url)
        if not normalized:
            w.fail("invalid_repository_url")
        return [dict(row) for row in self.db.execute(
            "SELECT p.id,p.url,p.title,p.abstract FROM links AS l "
            "JOIN papers AS p ON p.id=l.paper_id WHERE l.repo_url=? "
            "ORDER BY l.official DESC,l.in_paper DESC,l.in_repo DESC,p.id LIMIT ?",
            (normalized, limit))]

    def links(self, key, limit=MAX_LINKS):
        w.integer(limit, 1, 1000)
        return [dict(row) for row in self.db.execute(
            "SELECT repo_url,official,in_paper,in_repo FROM links WHERE paper_id=? "
            "ORDER BY official DESC,in_paper DESC,in_repo DESC,repo_url LIMIT ?", (key, limit))]

    def observations(self, plan, query_id, limit=12, paper_ids=None, exact_title=None, repository=None):
        plan = w.validate_plan(plan)
        query = next((row for row in plan["queries"] if row["id"] == query_id and
                      row["provider"] == "paperswithcode"), None)
        if not query:
            w.fail("catalog_query_required")
        if sum(value is not None for value in (paper_ids, exact_title, repository)) > 1:
            w.fail("ambiguous_catalog_lookup")
        w.integer(limit, 1, MAX_PAPERS)
        if paper_ids is not None:
            if not isinstance(paper_ids, list) or not 1 <= len(paper_ids) <= discovery.MAX_PAPER_LOOKUPS:
                w.fail("invalid_paper_lookup_count")
            normalized = [w.normalized_arxiv(value) for value in paper_ids]
            if len(set(normalized)) != len(normalized):
                w.fail("duplicate_paper_lookup")
            papers = [row for value in paper_ids if (row := self.lookup(value)) is not None]
        elif exact_title is not None:
            papers = self.lookup_title(exact_title, limit)
        elif repository is not None:
            papers = self.papers_for_repository(repository, limit)
        else:
            papers = self.search(query["native_query"], limit)
        results = []
        for row in papers:
            key = row["id"]
            stored = self.db.execute("SELECT url FROM papers WHERE id=?", (key,)).fetchone()
            if not stored:
                w.fail("invalid_catalog_database")
            url = stored["url"]
            refs = self.links(key)
            common = {"query_id": query_id, "origin": "local_catalog", "access": "metadata",
                      "catalog_snapshot": self.metadata["snapshot"], "catalog_license": self.metadata["license"]}
            paper = dict(common, kind="paper", url=url, title=row["title"], snippet=row["abstract"],
                         arxiv_id=key.removeprefix("arxiv:") if key.startswith("arxiv:") else None,
                         publication_hint="Local catalog metadata; verify original publication")
            try:
                w.normalize_result(paper, {query_id: query})
            except w.WorkflowError:
                continue
            results.append(paper)
            for ref in refs:
                note = ("Local catalog official flag; verify current relationship" if ref["official"]
                        else "Local catalog linked repository; verify relationship")
                code = dict(common, kind="repository", url=ref["repo_url"],
                            title=ref["repo_url"].removeprefix("https://github.com/"),
                            snippet=row["title"], publication_hint=note,
                            links=[{"url": url, "relation": "implements" if ref["official"] else "describes",
                                    "basis": "metadata", "note": note}])
                try:
                    w.normalize_result(code, {query_id: query})
                except w.WorkflowError:
                    continue
                results.append(code)
        return {"schema_version": 1, "scope": "local_catalog_discovery", "notice": NOTICE,
                "plan_id": w.plan_fingerprint(plan), "catalog": self.metadata,
                "query_id": query_id, "local_mode": ("identifier" if paper_ids else
                    "exact_title" if exact_title is not None else
                    "repository_reverse" if repository is not None else "keyword"),
                "papers_returned": len(papers), "results": results, "searches": []}


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True, parser_class=core.SafeArgumentParser)
    build = sub.add_parser("build")
    build.add_argument("--input", type=Path, required=True)
    build.add_argument("--database", type=Path, required=True)
    build.add_argument("--source", default="user-supplied metadata")
    build.add_argument("--license", default="unknown")
    build.add_argument("--snapshot", default="unknown")
    build.add_argument("--output", type=Path)
    find = sub.add_parser("search")
    find.add_argument("--database", type=Path, required=True)
    find.add_argument("--plan", type=Path, required=True)
    find.add_argument("--query-id", required=True)
    mode = find.add_mutually_exclusive_group()
    mode.add_argument("--paper-id", action="append")
    mode.add_argument("--exact-title")
    mode.add_argument("--repository")
    find.add_argument("--limit", type=int, default=12)
    find.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            report = build_catalog(args.input, args.database, args.source, args.license, args.snapshot)
        else:
            with Catalog(args.database) as catalog:
                report = catalog.observations(w.read_json(args.plan), args.query_id, args.limit, args.paper_id,
                                              args.exact_title, args.repository)
        w.write_json(report, args.output)
        return 0
    except (w.WorkflowError, OSError, ValueError, TypeError, RecursionError, sqlite3.Error) as error:
        code = str(error) if isinstance(error, w.WorkflowError) else "catalog_input_or_sqlite_error"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
