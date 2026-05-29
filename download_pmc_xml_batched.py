#!/usr/bin/env python3
"""
Download PMC full-text XML in batches and split the result into one file per PMCID.
"""

from __future__ import annotations

import argparse
import csv
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List


EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def read_pmcids(csv_path: Path) -> List[str]:
    with csv_path.open("r", newline="", encoding="utf-8") as csvfile:
        rows = csv.DictReader(csvfile)
        return [row["pmcid"].strip() for row in rows if row.get("pmcid", "").strip()]


def iter_unique(items: Iterable[str]) -> List[str]:
    seen = set()
    ordered = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def chunked(items: List[str], size: int) -> List[List[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_batch(pmcids: List[str], email: str | None, api_key: str | None) -> bytes:
    params = {
        "db": "pmc",
        "id": ",".join(pmcids),
        "retmode": "xml",
    }
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key

    url = f"{EFETCH_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url) as response:
        return response.read()


def extract_pmcid(article: ET.Element) -> str:
    for node in article.findall(".//front/article-meta/article-id"):
        if node.attrib.get("pub-id-type") == "pmcid" and node.text:
            return node.text.strip()
    return ""


def split_and_write(xml_bytes: bytes, output_dir: Path) -> int:
    root = ET.fromstring(xml_bytes)
    saved = 0

    if root.tag == "article":
        articles = [root]
    else:
        articles = root.findall("article")

    for article in articles:
        pmcid = extract_pmcid(article)
        if not pmcid:
            continue
        article_bytes = ET.tostring(article, encoding="utf-8", xml_declaration=True)
        (output_dir / f"{pmcid}.xml").write_bytes(article_bytes)
        saved += 1
    return saved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-download PMC XML files.")
    parser.add_argument(
        "--input",
        default="pubmed_results_pmc_only.csv",
        help="Input CSV containing a pmcid column. Default: pubmed_results_pmc_only.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="pmc_xml_batched",
        help="Directory to save XML files. Default: pmc_xml_batched",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Number of PMCID values per efetch request. Default: 20.",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Optional contact email for NCBI API etiquette.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional NCBI API key for higher rate limits.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.34,
        help="Delay between batch requests. Default: 0.34 seconds.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on number of XML files to download.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pmcids = iter_unique(read_pmcids(input_path))
    if args.limit is not None:
        pmcids = pmcids[: args.limit]

    batches = chunked(pmcids, args.batch_size)
    print(f"Preparing {len(batches)} batch request(s) for {len(pmcids)} PMC XML file(s)")

    written = 0
    for index, batch in enumerate(batches, start=1):
        xml_bytes = fetch_batch(batch, args.email, args.api_key)
        saved = split_and_write(xml_bytes, output_dir)
        written += saved
        print(f"[{index}/{len(batches)}] Saved {saved} article XML file(s); cumulative={written}")
        time.sleep(args.sleep_seconds)

    print(f"Finished. Wrote {written} XML files into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
