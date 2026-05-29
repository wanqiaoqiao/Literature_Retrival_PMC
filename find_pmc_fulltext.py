#!/usr/bin/env python3
"""
Annotate PubMed CSV records with PMC full-text availability.

Reads a CSV created by pubmed_fetch.py, looks up PMCID values for PMID records
via the NCBI PMC ID Converter API, and writes:
  1. A full CSV with added pmcid / has_pmc_fulltext columns
  2. A subset CSV containing only records with PMC full text
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List


IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"


def http_get_json(params: Dict[str, str]) -> Dict:
    url = f"{IDCONV_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def chunked(items: List[str], size: int) -> List[List[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csvfile:
        return list(csv.DictReader(csvfile))


def write_rows(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def lookup_pmcids(pmids: List[str], email: str | None, tool: str, batch_size: int, sleep_seconds: float) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for index, batch in enumerate(chunked(pmids, batch_size), start=1):
        print(f"Looking up batch {index}: {len(batch)} PMID(s)")
        params = {
            "ids": ",".join(batch),
            "idtype": "pmid",
            "format": "json",
            "tool": tool,
        }
        if email:
            params["email"] = email

        data = http_get_json(params)
        for record in data.get("records", []):
            pmid = str(record.get("pmid", "")).strip()
            pmcid = str(record.get("pmcid", "")).strip()
            if pmid and pmcid:
                mapping[pmid] = pmcid

        time.sleep(sleep_seconds)
    return mapping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find which PubMed records have PMC full text.")
    parser.add_argument(
        "--input",
        default="pubmed_results.csv",
        help="Input PubMed CSV path. Default: pubmed_results.csv",
    )
    parser.add_argument(
        "--output-all",
        default="pubmed_results_with_pmc.csv",
        help="Annotated output CSV path. Default: pubmed_results_with_pmc.csv",
    )
    parser.add_argument(
        "--output-pmc-only",
        default="pubmed_results_pmc_only.csv",
        help="PMC-only output CSV path. Default: pubmed_results_pmc_only.csv",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Optional contact email for NCBI API etiquette.",
    )
    parser.add_argument(
        "--tool",
        default="codex-pmc-check",
        help="Tool name sent to NCBI. Default: codex-pmc-check",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="PMID lookup batch size. Default: 200.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.34,
        help="Delay between API requests. Default: 0.34 seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    output_all_path = Path(args.output_all)
    output_pmc_only_path = Path(args.output_pmc_only)

    rows = read_rows(input_path)
    pmids = [row["pmid"].strip() for row in rows if row.get("pmid", "").strip()]
    print(f"Loaded {len(rows)} rows and {len(pmids)} PMID values from {input_path}")

    mapping = lookup_pmcids(
        pmids=pmids,
        email=args.email,
        tool=args.tool,
        batch_size=args.batch_size,
        sleep_seconds=args.sleep_seconds,
    )

    annotated_rows: List[Dict[str, str]] = []
    pmc_only_rows: List[Dict[str, str]] = []

    for row in rows:
        pmid = row.get("pmid", "").strip()
        pmcid = mapping.get(pmid, "")
        annotated = dict(row)
        annotated["pmcid"] = pmcid
        annotated["has_pmc_fulltext"] = "yes" if pmcid else "no"
        if pmcid:
            annotated["pmc_url"] = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
            pmc_only_rows.append(annotated)
        else:
            annotated["pmc_url"] = ""
        annotated_rows.append(annotated)

    fieldnames = list(rows[0].keys()) + ["pmcid", "has_pmc_fulltext", "pmc_url"]
    write_rows(output_all_path, annotated_rows, fieldnames)
    write_rows(output_pmc_only_path, pmc_only_rows, fieldnames)

    print(f"Annotated CSV written to {output_all_path}")
    print(f"PMC-only CSV written to {output_pmc_only_path}")
    print(f"Found {len(pmc_only_rows)} records with PMC full text")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
