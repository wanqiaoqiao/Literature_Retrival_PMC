# PubMed to PMC Full-Text XML Pipeline

This repository contains three Python scripts that work together to search PubMed, identify which PubMed records have full text available in PubMed Central (PMC), and download the corresponding PMC full-text XML files.

## Overview

The workflow has three steps:

```text
1. Search PubMed and save metadata
   pubmed_fetch.py
        ↓
   pubmed_results.csv

2. Find which PubMed records have PMC full text
   find_pmc_fulltext.py
        ↓
   pubmed_results_with_pmc.csv
   pubmed_results_pmc_only.csv

3. Download PMC full-text XML files
   download_pmc_xml_batched.py
        ↓
   pmc_xml_batched/*.xml
```

## Scripts

### 1. `pubmed_fetch.py`

Searches PubMed using NCBI E-utilities and saves article metadata to a CSV file.

By default, it searches for:

* `"iPSC differentiation protocol"`
* `"directed differentiation stem cell"`
* `"pluripotent stem cell differentiation method"`

The output CSV includes fields such as:

```text
pmid
title
journal
pub_date
doi
authors
keywords
abstract
pubmed_url
```

Example:

```bash
python pubmed_fetch.py \
  --email your_email@example.com \
  --output pubmed_results.csv
```

Custom query terms can be provided with `--terms`:

```bash
python pubmed_fetch.py \
  --terms "iPSC differentiation protocol" "pancreatic beta cell differentiation" \
  --max-results 5000 \
  --email your_email@example.com \
  --output pubmed_results.csv
```

### 2. `find_pmc_fulltext.py`

Reads the PubMed CSV produced by `pubmed_fetch.py`, uses the NCBI PMC ID Converter API to map PMID values to PMCID values, and writes two output files:

```text
pubmed_results_with_pmc.csv
pubmed_results_pmc_only.csv
```

The full output file contains all original PubMed records plus:

```text
pmcid
has_pmc_fulltext
pmc_url
```

The PMC-only output file contains only records that have a PMCID.

Example:

```bash
python find_pmc_fulltext.py \
  --input pubmed_results.csv \
  --output-all pubmed_results_with_pmc.csv \
  --output-pmc-only pubmed_results_pmc_only.csv \
  --email your_email@example.com
```

This script is the bridge between PubMed metadata and PMC full-text XML download.

### 3. `download_pmc_xml_batched.py`

Reads a CSV file containing a `pmcid` column and downloads the corresponding PMC full-text XML files in batches.

The expected input is usually:

```text
pubmed_results_pmc_only.csv
```

Example:

```bash
python download_pmc_xml_batched.py \
  --input pubmed_results_pmc_only.csv \
  --output-dir pmc_xml_batched \
  --email your_email@example.com
```

Each downloaded article is saved as a separate XML file:

```text
pmc_xml_batched/PMC1234567.xml
pmc_xml_batched/PMC2345678.xml
pmc_xml_batched/PMC3456789.xml
```

## Complete Workflow

Run the three scripts in this order:

```bash
python pubmed_fetch.py \
  --email your_email@example.com \
  --output pubmed_results.csv

python find_pmc_fulltext.py \
  --input pubmed_results.csv \
  --output-all pubmed_results_with_pmc.csv \
  --output-pmc-only pubmed_results_pmc_only.csv \
  --email your_email@example.com

python download_pmc_xml_batched.py \
  --input pubmed_results_pmc_only.csv \
  --output-dir pmc_xml_batched \
  --email your_email@example.com
```

After running the full pipeline, the main outputs are:

```text
pubmed_results.csv
pubmed_results_with_pmc.csv
pubmed_results_pmc_only.csv
pmc_xml_batched/
```

## Recommended Test Run

Before downloading many files, run a small test:

```bash
python pubmed_fetch.py \
  --terms "iPSC differentiation protocol" \
  --max-results 20 \
  --email your_email@example.com \
  --output test_pubmed_results.csv

python find_pmc_fulltext.py \
  --input test_pubmed_results.csv \
  --output-all test_pubmed_results_with_pmc.csv \
  --output-pmc-only test_pubmed_results_pmc_only.csv \
  --email your_email@example.com

python download_pmc_xml_batched.py \
  --input test_pubmed_results_pmc_only.csv \
  --output-dir test_pmc_xml \
  --limit 5 \
  --email your_email@example.com
```

This confirms that the pipeline works before running a larger search.

## Requirements

The scripts use only the Python standard library.

Tested with:

```text
Python 3.10+
```

No additional packages are required.

## Important Input and Output Compatibility

The scripts are designed to work together through CSV files.

`pubmed_fetch.py` creates:

```text
pubmed_results.csv
```

This file contains a `pmid` column.

`find_pmc_fulltext.py` reads the `pmid` column and creates:

```text
pubmed_results_pmc_only.csv
```

This file contains a `pmcid` column.

`download_pmc_xml_batched.py` requires a CSV with a `pmcid` column.

Therefore, do not pass `pubmed_results.csv` directly into `download_pmc_xml_batched.py`. It will not work because the original PubMed CSV does not contain PMC IDs.

Correct:

```bash
python download_pmc_xml_batched.py --input pubmed_results_pmc_only.csv
```

Incorrect:

```bash
python download_pmc_xml_batched.py --input pubmed_results.csv
```

## Useful Options

### `pubmed_fetch.py`

```text
--terms              Search terms or phrases
--max-results        Maximum number of PubMed records to fetch
--batch-size         Number of records fetched per PubMed request
--output             Output CSV path
--email              Contact email for NCBI
--api-key            Optional NCBI API key
--sleep-seconds      Delay between API requests
```

### `find_pmc_fulltext.py`

```text
--input              Input PubMed CSV
--output-all         Output CSV with all rows annotated
--output-pmc-only    Output CSV containing only rows with PMC full text
--email              Contact email for NCBI
--tool               Tool name sent to NCBI
--batch-size         Number of PMID values checked per request
--sleep-seconds      Delay between API requests
```

### `download_pmc_xml_batched.py`

```text
--input              Input CSV containing a pmcid column
--output-dir         Directory to save XML files
--batch-size         Number of PMCIDs per download request
--email              Contact email for NCBI
--api-key            Optional NCBI API key
--sleep-seconds      Delay between API requests
--limit              Optional cap on number of XML files to download
```

## Recommended NCBI Usage

When using NCBI APIs, provide an email address:

```bash
--email your_email@example.com
```

For larger jobs, consider using an NCBI API key:

```bash
--api-key YOUR_NCBI_API_KEY
```

The scripts include a default delay between requests using `--sleep-seconds`. Avoid setting this too low for large downloads.

## Known Limitation

Not every PubMed article has full text available in PMC. The first script may return many PubMed records, but only a subset will have PMC full-text XML.

For example:

```text
PubMed results: 10,000
PMC full-text records: 2,300
Downloaded XML files: 2,300
```

This is expected behavior.

## Suggested Small Code Safety Improvement

In `find_pmc_fulltext.py`, the script assumes the input CSV has at least one row. If the PubMed search returns zero rows, this line may fail:

```python
fieldnames = list(rows[0].keys()) + ["pmcid", "has_pmc_fulltext", "pmc_url"]
```

A safe check can be added after reading the input rows:

```python
if not rows:
    print(f"No rows found in {input_path}")
    return 0
```

## Example Output Structure

After a successful run:

```text
project/
├── pubmed_fetch.py
├── find_pmc_fulltext.py
├── download_pmc_xml_batched.py
├── pubmed_results.csv
├── pubmed_results_with_pmc.csv
├── pubmed_results_pmc_only.csv
└── pmc_xml_batched/
    ├── PMC1234567.xml
    ├── PMC2345678.xml
    └── PMC3456789.xml
```

## License and Reuse Note

PMC XML files may have different licenses depending on the article. Before redistributing, text-mining at scale, or using article contents commercially, check the license information associated with each PMC article.

## Summary

Use the scripts in this order:

```text
pubmed_fetch.py
→ find_pmc_fulltext.py
→ download_pmc_xml_batched.py
```

The key handoff is:

```text
pubmed_results.csv
→ pubmed_results_pmc_only.csv
→ pmc_xml_batched/*.xml
```
