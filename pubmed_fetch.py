#!/usr/bin/env python3
"""
Fetch up to 10,000 PubMed records with the NCBI E-utilities API.

Default query terms:
  - "iPSC differentiation protocol"
  - "directed differentiation stem cell"
  - "pluripotent stem cell differentiation method"

Example:
  python pubmed_fetch.py --email your_email@example.com --output pubmed_results.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

DEFAULT_TERMS = [
    "iPSC differentiation protocol",
    "directed differentiation stem cell",
    "pluripotent stem cell differentiation method",
]


def build_query(terms: Iterable[str]) -> str:
    cleaned = [term.strip() for term in terms if term.strip()]
    if not cleaned:
        raise ValueError("At least one non-empty query term is required.")
    return " OR ".join(f'"{term}"' for term in cleaned)


def http_get(url: str, params: Dict[str, str]) -> bytes:
    query = urllib.parse.urlencode(params)
    request_url = f"{url}?{query}"
    with urllib.request.urlopen(request_url) as response:
        return response.read()


def esearch(query: str, max_results: int, email: Optional[str], api_key: Optional[str]) -> Dict[str, str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retstart": "0",
        "retmode": "xml",
        "usehistory": "y",
        "sort": "relevance",
    }
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key

    root = ET.fromstring(http_get(ESEARCH_URL, params))
    count = root.findtext("Count", default="0")
    webenv = root.findtext("WebEnv")
    query_key = root.findtext("QueryKey")

    if not webenv or not query_key:
        raise RuntimeError("PubMed esearch did not return WebEnv/QueryKey.")

    return {
        "count": count,
        "webenv": webenv,
        "query_key": query_key,
    }


def get_text(node: Optional[ET.Element]) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def parse_pub_date(article: ET.Element) -> str:
    pub_date = article.find(".//JournalIssue/PubDate")
    if pub_date is None:
        return ""

    medline_date = pub_date.findtext("MedlineDate")
    if medline_date:
        return medline_date.strip()

    year = pub_date.findtext("Year", default="").strip()
    month = pub_date.findtext("Month", default="").strip()
    day = pub_date.findtext("Day", default="").strip()
    return "-".join(part for part in [year, month, day] if part)


def parse_authors(article: ET.Element) -> str:
    authors = []
    for author in article.findall(".//AuthorList/Author"):
        collective_name = author.findtext("CollectiveName")
        if collective_name:
            authors.append(collective_name.strip())
            continue

        last_name = author.findtext("LastName", default="").strip()
        fore_name = author.findtext("ForeName", default="").strip()
        initials = author.findtext("Initials", default="").strip()

        if last_name and fore_name:
            authors.append(f"{fore_name} {last_name}")
        elif last_name and initials:
            authors.append(f"{initials} {last_name}")
        elif last_name:
            authors.append(last_name)

    return "; ".join(authors)


def parse_keywords(article: ET.Element) -> str:
    keywords = [get_text(node) for node in article.findall(".//KeywordList/Keyword")]
    filtered = [kw for kw in keywords if kw]
    return "; ".join(filtered)


def parse_doi(article: ET.Element) -> str:
    for article_id in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
        if article_id.attrib.get("IdType") == "doi":
            return get_text(article_id)
    return ""


def parse_abstract(article: ET.Element) -> str:
    sections = []
    for abstract_text in article.findall(".//Abstract/AbstractText"):
        label = abstract_text.attrib.get("Label", "").strip()
        text = get_text(abstract_text)
        if not text:
            continue
        if label:
            sections.append(f"{label}: {text}")
        else:
            sections.append(text)
    return " ".join(sections)


def parse_article(pubmed_article: ET.Element) -> Dict[str, str]:
    medline = pubmed_article.find("MedlineCitation")
    article = medline.find("Article") if medline is not None else None

    pmid = medline.findtext("PMID", default="").strip() if medline is not None else ""
    title = get_text(article.find("ArticleTitle")) if article is not None else ""
    journal = get_text(article.find("Journal/Title")) if article is not None else ""
    pub_date = parse_pub_date(article) if article is not None else ""
    abstract = parse_abstract(article) if article is not None else ""
    authors = parse_authors(article) if article is not None else ""
    keywords = parse_keywords(pubmed_article)
    doi = parse_doi(pubmed_article)

    return {
        "pmid": pmid,
        "title": title,
        "journal": journal,
        "pub_date": pub_date,
        "doi": doi,
        "authors": authors,
        "keywords": keywords,
        "abstract": abstract,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
    }


def efetch_batch(
    webenv: str,
    query_key: str,
    start: int,
    batch_size: int,
    email: Optional[str],
    api_key: Optional[str],
) -> List[Dict[str, str]]:
    params = {
        "db": "pubmed",
        "query_key": query_key,
        "WebEnv": webenv,
        "retstart": str(start),
        "retmax": str(batch_size),
        "retmode": "xml",
    }
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key

    root = ET.fromstring(http_get(EFETCH_URL, params))
    records = []
    for pubmed_article in root.findall("PubmedArticle"):
        records.append(parse_article(pubmed_article))
    return records


def write_csv(records: List[Dict[str, str]], output_path: str) -> None:
    fieldnames = [
        "pmid",
        "title",
        "journal",
        "pub_date",
        "doi",
        "authors",
        "keywords",
        "abstract",
        "pubmed_url",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch PubMed records by keyword.")
    parser.add_argument(
        "--terms",
        nargs="+",
        default=DEFAULT_TERMS,
        help="Query phrases. Default: the three stem-cell differentiation phrases.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10000,
        help="Maximum number of PubMed records to fetch. Default: 10000.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Records fetched per efetch request. Default: 200.",
    )
    parser.add_argument(
        "--output",
        default="pubmed_results.csv",
        help="Output CSV path. Default: pubmed_results.csv",
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
        help="Delay between efetch requests. Default: 0.34 seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    query = build_query(args.terms)

    print(f"Search query: {query}")
    search_info = esearch(query, args.max_results, args.email, args.api_key)
    total_found = int(search_info["count"])
    target = min(total_found, args.max_results)
    print(f"PubMed matched {total_found} records; fetching {target}.")

    if target == 0:
        write_csv([], args.output)
        print(f"No records found. Empty CSV written to {args.output}")
        return 0

    all_records: List[Dict[str, str]] = []
    for start in range(0, target, args.batch_size):
        batch_size = min(args.batch_size, target - start)
        print(f"Fetching records {start + 1}-{start + batch_size}...")
        batch_records = efetch_batch(
            webenv=search_info["webenv"],
            query_key=search_info["query_key"],
            start=start,
            batch_size=batch_size,
            email=args.email,
            api_key=args.api_key,
        )
        all_records.extend(batch_records)
        time.sleep(args.sleep_seconds)

    write_csv(all_records, args.output)
    print(f"Saved {len(all_records)} records to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        raise SystemExit(130)
