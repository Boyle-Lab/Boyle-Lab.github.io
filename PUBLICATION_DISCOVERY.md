# Automated publication discovery

This repository includes a conservative discovery system that checks PubMed and bioRxiv for Alan P. Boyle publications that are absent from the authoritative bibliography. It proposes changes through a draft pull request; it does not merge records automatically.

The system is implemented by:

```text
.github/workflows/discover-publications.yml
publication_discovery.yml
scripts/discover_publications.py
scripts/publication_discovery.py
tests/test_publication_discovery.py
```

## Authoritative files and generated outputs

Discovery edits only the authoritative inputs:

```text
bibliography/publications.bib
publication_metadata/<citation-key>.yml
```

The existing publication and CV builders then regenerate:

```text
_papers/<CitationKey>.yml
pub.bib
cv/generated/publications.tex
assets/ABoyle_CV.pdf
```

`bibliography/publications.bib` remains the master bibliography. New records receive the same stable, filename-safe citation-key format used elsewhere in the repository. A new record also receives a minimal sidecar containing the permanent `bibkey`, inferred Boyle Lab member `umid` values, and any publication-specific author-name mapping needed by the normal publication builder.

## External sources

### PubMed

The script queries the NCBI E-utilities author index using Alan Boyle's ORCID, full author name, and surname-plus-initials forms. The name, email, and ORCID are read from the `_people` record with the configured Michigan `umid`.

PubMed candidates are fetched as structured XML and converted to BibTeX fields for author order, title, journal, volume, issue, pages or electronic article number, publication date, DOI, PMID, abstract, and primary URL.

Corrections, retractions, editorials, comments, and news items are excluded by default. The exclusions can be changed in `publication_discovery.yml`.

### bioRxiv

The official bioRxiv API does not provide a general author-search endpoint. The scheduled workflow therefore scans a rolling 21-day interval and filters the returned records by the target author. The overlap protects against delayed indexing and an occasional missed workflow run.

A manual run can use an explicit start date for a historical backfill. Use moderate intervals, such as one calendar year at a time, rather than querying the complete bioRxiv archive in one request series.

The script retains only the newest version of each bioRxiv DOI. Values such as `NA` in the API's `published` field are normalized to an empty value so unrelated unpublished preprints cannot be conflated.

## Conservative author matching

A candidate is eligible for automatic addition only when Alan Boyle's authorship is supported by one of the following:

1. An exact ORCID match.
2. A full first-name and surname match.
3. A compatible indexed name plus a configured institutional affiliation.

Initials alone are not sufficient. Records that cannot be confirmed with high confidence are excluded from automatic changes.

Lab-member relationships are inferred from `_people/*.md` and historical publication-specific aliases already present in `publication_metadata/*.yml`. The pull request checklist still requires review of every inferred member relationship.

## Duplicate and preprint handling

Before a record is added, the script compares it with the master bibliography using:

- DOI;
- PMID;
- normalized title;
- first-author-aware title similarity; and
- the official bioRxiv published-article relationship endpoint.

An exact DOI or PMID match is always treated as already present. A close but uncertain title match is reported for manual review and is not added.

When PubMed identifies the journal version of an existing bioRxiv paper and the bioRxiv API provides an explicit relationship, the script updates the existing record while retaining its permanent citation key. The prior preprint link remains in the `biorxiv` field.

## Scheduled workflow

The workflow runs every Monday at 07:17 UTC, which falls within NCBI's recommended overnight period in Michigan. It can also be launched manually from the Actions tab.

A workflow run performs these steps:

1. Stops without changing files when a prior automated discovery pull request remains open. This protects manual edits under review.
2. Queries PubMed and bioRxiv.
3. Applies only high-confidence additions and explicit preprint-to-journal upgrades.
4. Regenerates publication YAML, `pub.bib`, the CV publication source, and the CV PDF.
5. Runs the repository test suite.
6. Pushes the result to `automation/publication-discovery`.
7. Opens a draft pull request with a review table and checklist.

The workflow requests only the repository permissions needed to push a branch and create a pull request:

```yaml
permissions:
  contents: write
  pull-requests: write
```

### Required repository setting

GitHub repository settings must also permit GitHub Actions to create pull requests. In **Settings → Actions → General → Workflow permissions**, enable **Allow GitHub Actions to create and approve pull requests**.

An NCBI API key is optional. To use one, create a repository Actions secret named:

```text
NCBI_API_KEY
```

Without a key, the HTTP client limits itself to fewer than three NCBI requests per second.

## Manual workflow inputs

The manual workflow supports:

```text
sources
    all, pubmed, or biorxiv

lookback_days
    Rolling bioRxiv interval; ignored when biorxiv_start_date is set

biorxiv_start_date
    Optional explicit YYYY-MM-DD start date for a backfill
```

For an initial recent backfill, a reasonable manual run is:

```text
sources: all
lookback_days: 180
biorxiv_start_date: [leave blank]
```

For older bioRxiv records, run one year at a time and review each resulting pull request before continuing.

## Local use

Install the publication dependencies:

```bash
python3 -m pip install --requirement requirements-publications.txt
```

Preview proposed changes without editing the repository:

```bash
make discover-publications-dry-run
```

Apply high-confidence changes locally:

```bash
make discover-publications
make publications
make cv
make test
```

Equivalent direct commands are:

```bash
python3 scripts/discover_publications.py --dry-run
python3 scripts/discover_publications.py
```

Use only PubMed:

```bash
python3 scripts/discover_publications.py --sources pubmed
```

Backfill bioRxiv for a defined interval:

```bash
python3 scripts/discover_publications.py \
  --sources biorxiv \
  --biorxiv-start-date 2025-01-01
```

Reports are written to:

```text
.publication-discovery/report.md
.publication-discovery/result.json
```

The directory is ignored by Git.

## Pull-request review

Before merging an automated publication pull request, confirm:

- Alan P. Boyle is a byline author rather than a namesake or non-byline collaborator.
- The title, author order, journal, date, volume, issue, pages, DOI, PMID, and abstract are correct.
- Equal-contribution and co-senior-author markers are restored when the external index does not encode them.
- The stable citation key is suitable and should remain permanent.
- Every inferred `members` value and `author_member_map` entry is correct.
- A journal article is truly the published version of any preprint being upgraded.
- Website-only fields such as `summary`, `topics`, `featured`, `teaser`, `links`, and news relationships are added when appropriate.

The workflow intentionally favors false negatives over false positives. A record that cannot be linked safely remains out of the bibliography until it is reviewed manually.
