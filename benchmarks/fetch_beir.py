#!/usr/bin/env python3
"""Explicit benchmark-only download of a revision-pinned public data set.

No repository secrets, cookies, user case records or model credentials are
used. The production skill and its standard-library CLI remain offline.
"""
import argparse
import hashlib
from pathlib import Path
import urllib.request
from full_catalog import FixedPublicRedirect

BASE = "https://huggingface.co/datasets/BeIR/cqadupstack/resolve/e84b7220ce5a4e6c49aeb568983b0ec5a7584c2c/programmers"
QRELS = "https://huggingface.co/datasets/BeIR/cqadupstack-qrels/resolve/2b9f5791698b5be7bc5e10535c8690f20043c3db/programmers/test.tsv"
FILES = (
    ("corpus.parquet", BASE + "/corpus/corpus-00000-of-00001.parquet",
     "b8eefa212252fe5af6ee72ba530df053740ff30c2c0bea77089f8a9271e94f75", 32 * 1024 * 1024),
    ("queries.parquet", BASE + "/queries/queries-00000-of-00001.parquet",
     "106ba4777034ccec608a623ac93b5cfad63d89effc64d0528759ea94e276345d", 1024 * 1024),
    ("test.tsv", QRELS, None, 1024 * 1024),
)


def download(destination):
    destination.mkdir()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), FixedPublicRedirect())
    for filename, url, expected, limit in FILES:
        target = destination / filename
        with opener.open(url, timeout=90) as response:
            if not response.url.startswith("https://"):
                raise ValueError("Non-HTTPS dataset response")
            data = response.read(limit + 1)
        if not data or len(data) > limit:
            raise ValueError("Public data outside expected bounds")
        actual = hashlib.sha256(data).hexdigest()
        if expected is not None and actual != expected:
            raise ValueError("Public parquet digest mismatch")
        with target.open("xb") as output:
            output.write(data)
        print(filename, len(data), actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    download(args.output)


if __name__ == "__main__":
    main()
