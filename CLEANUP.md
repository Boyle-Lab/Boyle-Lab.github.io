# Repository cleanup record

This cleanup was performed against the repository supplied on August 10, 2026. Files were removed only when they had no active template, content, download, or dynamic Jekyll code path, or when an identical canonical copy remained. The cleanup removes 32 files totaling approximately 9.5 MB and reduces `main_style.css` from 51,566 to 44,273 bytes while preserving every selector used by the current site.

## Removed layouts and includes

```text
_layouts/simple.html
_includes/reference_paper.html
_includes/pub/pub.html
_includes/pub/pub_bib.html
```

These belonged to the former generated HTML bibliography or an unused page shell. The current site uses structured `_papers` records and the three active layouts: `default`, `member`, and `post`.

## Removed publication remnants

```text
scripts/migrate_legacy_publications.py
```

The migration has already been completed. The maintained pipeline is `publication_tools.py`, `build_publications.py`, and `scaffold_publication_metadata.py`.

Obsolete generated search assets are also rejected and removed by the publication builder if they reappear:

```text
assets/data/publications.json
assets/js/publications.js
```

The Publications page is intentionally static, with no search, filter, or visitor-controlled sorting interface.

## Removed duplicate or unused CSS/font files

```text
css/academicons.min.css
fonts/academicons.eot
fonts/academicons.svg
fonts/academicons.ttf
```

The site loads only `css/academicons.css` and `fonts/academicons.woff`.

Legacy selectors were removed from `main_style.css`, including the former banner/header system, table navigation, floated people and news grids, superseded homepage columns, obsolete publication controls, and old post headings. The remaining CSS selectors are referenced by current templates or are the two Liquid-generated hero modifiers.

## Removed duplicate and unused root files

```text
boyle_lab.ico
F-Seq/bffBuilder.tgz
assets/job_PDFs/TechAssoc.pdf
assets/reg.png
```

The canonical favicon is `assets/boyle_lab.ico`. `assets/images/reg.jpg` remains the Research-page image.

## Removed unused legacy images

```text
assets/images/DNA_Cloud.png
assets/images/DNA_Cloud_small.png
assets/images/Fseq.gif
assets/images/MSRB1-2-3.jpg
assets/images/SOMcluster-01.png
assets/images/Stanford-seal-small.gif
assets/images/banner-landing.jpg
assets/images/banner-short-apb.png
assets/images/breast_cancer.PNG
assets/images/nanopore_sequencers.jpg
assets/images/nanopore_sequencers_crop.jpg
assets/images/palmer.png
assets/images/reg.png
assets/images/regulomedb_logo.png
assets/images/science_alan.jpg
assets/images/science_alan_crop.jpg
assets/images/social-icons.png
assets/images/sustainable_lab_icon.png
assets/images/white_matrix.jpg
```

These files were remnants of prior layouts and were not referenced by current pages, posts, templates, CSS, or structured data.

## Deliberately retained material

The cleanup did not remove:

- `assets/news_graphics/`, including older galleries. Some posts discover gallery files dynamically and old public URLs may be in circulation.
- `pubs/`, because local paper PDFs are linked from citation data and may have external inbound links.
- Unpublished news and job records, because `published: false` or `publish: false` is the intended archive mechanism.
- Current and former member profiles, because alumni pages and publication relationships rely on stable `umid` records.
- Publication screenshots used by featured cards.

## Ongoing safeguards

`tests/test_site_structure.py` verifies that known legacy paths remain absent, all Liquid includes and layouts resolve, CSS parses, and every static CSS class is referenced. `build_publications.py` removes obsolete generated publication files and fails in check mode when output is stale.
