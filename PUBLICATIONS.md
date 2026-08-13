# Publication data and build pipeline

The publication system separates portable citation data from website-only metadata while preserving BibTeX as the source used for the CV.

## Data flow

```text
bibliography/publications.bib
        +
publication_metadata/*.yml
        +
_people/*.md
        |
        v
scripts/build_publications.py
        |
        +--> _papers/<BibTeXKey>.yml
        +--> pub.bib
```

### Authoritative files

- `bibliography/publications.bib`: authors, title, journal, year, volume, pages, DOI, PMID, URLs, abstract, and other citation fields.
- `publication_metadata/*.yml`: Michigan `umid` relationships and website-only fields.
- `_people/*.md`: canonical member names and profile URLs.

### Generated files

- `_papers/*.yml`: records consumed by Jekyll.
- `pub.bib`: combined bibliography used for download and CV workflows.

Never edit a generated paper file or `pub.bib` directly.

## Citation keys

Each BibTeX key is a permanent, filename-safe identifier:

```text
FirstAuthorYearMnemonic
```

Examples:

```text
Dong2023RegulomeDB2
McDonald2021Cas9MobileElements
VanDeynze2025HMMSTR
SMaHTNetwork2025SomaticMutationBenchmarking
```

Keys must match `^[A-Za-z][A-Za-z0-9]*$`, be unique without regard to filename case, and remain unchanged when a preprint becomes a journal article. The generated filename is exactly `_papers/<BibTeXKey>.yml`.

## Adding or updating a publication

1. Add or edit the entry in `bibliography/publications.bib`.
2. For a new key, create a sidecar:

   ```bash
   python3 scripts/scaffold_publication_metadata.py --bibkey NewKey2026
   ```

3. Review the inferred `members` list. The scaffold is conservative and cannot infer consortium participation or every historical author name.
4. Add any website-only fields described below.
5. Regenerate and test:

   ```bash
   make publications
   make check
   ```

6. Commit the BibTeX, sidecar, generated `_papers` record, and `pub.bib`.

The GitHub Actions workflow performs the same generation and will commit changed generated files after a direct push.

## Minimal sidecar

```yaml
bibkey: VanDeynze2025HMMSTR
members:
  - kvandeyn
  - crmumm
  - apboyle
```

`bibkey` must match one BibTeX entry. `members` contains Michigan `umid` values from `_people` in byline order when practical.

## Historical or publication-specific names

Do not add name aliases to `_people`. Map a specific byline in the relevant sidecar:

```yaml
bibkey: Mumm2023OnRamp
members:
  - melyssae
  - apboyle
author_member_map:
  melyssae: "Drexel, Melissa L"
```

The mapping value may be the exact BibTeX author name or a zero-based author index. Every mapped `umid` must also appear in `members`.

## Consortium and other non-byline participation

When a lab member participated through a group author but is not individually named in the BibTeX byline:

```yaml
members:
  - apboyle
member_roles:
  apboyle: consortium
```

Supported non-byline roles are `consortium`, `contributor`, `group_author`, and `non_byline`. The main Publications page displays a Consortium badge if any member role is `consortium`. An individual member page can show that person’s role without inserting a false personal byline.

## Website-only links

Citation fields should remain in BibTeX where possible. Sidecar `links` are for supplemental resources:

```yaml
links:
  code: https://github.com/example/tool
  data: https://example.org/dataset
  protocol: https://example.org/protocol
  news:
    - /papers/2026/01/01/example/
```

`news` is normalized to a list. Article, PDF, and preprint URLs should normally be BibTeX fields rather than duplicated in `links`.

## Featured publications

The Publications page shows up to four records with `featured: true`, newest first:

```yaml
featured: true
topics:
  - Tandem repeats
  - Long-read sequencing
  - Neurogenetics
summary: >-
  A concise plain-language description of the central result and why it matters.
teaser: /assets/images/publications/VanDeynze2025HMMSTR.png
```

The teaser should be a screenshot of the full first page of the paper, tightly cropped to the page boundary. The CSS scales the full page into the card without cropping it.

## Optional overrides

These fields are accepted when citation information cannot be represented appropriately in BibTeX:

```yaml
status: preprint          # published, preprint, or in_press
publication_type: article # article, chapter, or conference
PMID: "12345678"
biorxiv: https://...
abstract: >-
  Optional website-specific abstract override.
```

Prefer to maintain DOI, PMID, URLs, dates, abstracts, journal, volume, and pages in BibTeX.

## Generated paper schema

Every generated record contains:

```yaml
generated: true
bibkey: StableKey2026
title: Paper title
author_list:
  - citation_name: Boyle AP
    member_url: /people/Alan_Boyle/
    member_name: Alan P. Boyle, Ph.D.
    equal_contrib: true       # only when present
    co_senior: true           # only when present
year: 2026
sort_date: 2026-06-28
members:
  - apboyle
bibtex: |
  @article{StableKey2026,
    ...
  }
```

Optional generated fields are limited to those used by the current templates: `status`, `publication_type`, `journal`, `volume`, `number`, `pages`, `doi`, `PMID`, `primary_url`, `pdf`, `biorxiv`, `links`, `member_roles`, `abstract`, `featured`, `topics`, `summary`, and `teaser`.

The full author list is always serialized and displayed. There is no short or collapsible author representation.

## Validation rules

The build rejects or warns about:

- Unsafe or duplicate BibTeX keys.
- Duplicate DOIs.
- Missing sidecars or orphaned sidecars.
- Unknown or duplicate member `umid` values.
- Members that cannot be matched to the byline without an override or non-byline role.
- Invalid status, publication type, or role values.
- Duplicate filenames on case-insensitive filesystems.
- Deprecated `slug`, `legacy_bibkeys`, person alias fields, and obsolete generated assets.
- Stale or missing generated records in `--check` mode.

Run strict validation with:

```bash
python3 scripts/build_publications.py --check --strict
```
