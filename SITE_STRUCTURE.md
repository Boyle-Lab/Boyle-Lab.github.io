# Repository structure

This document identifies the role and ownership of each major file group. “Authored” files are edited directly. “Generated” files are replaced by scripts and should not be edited manually.

## Root files

| Path | Type | Purpose |
|---|---|---|
| `index.html` | Authored | Homepage with lab introduction, recent publications, and recent Lab Life posts. |
| `research.html` | Authored | Research overview and program areas. |
| `people.html` | Authored template | People index. Reads the `_people` collection. |
| `software.html` | Authored | Software and resource cards. |
| `publications.html` | Authored wrapper | Loads `_includes/publications_page.html`. |
| `pub_bib.html` | Authored template | Human-readable BibTeX page generated from `site.papers`. |
| `jobs.html` | Authored template | Reads the `_jobs` collection. |
| `contact.html` | Authored | Locations, maps, and contact information. |
| `pub.bib` | Generated | Combined downloadable bibliography. |
| `CV.md` | Documentation | CV source, generation, and deployment guide. |
| `_config.yml` | Configuration | Jekyll collections, pagination, defaults, and build exclusions. |
| `CNAME` | Deployment | Custom domain for GitHub Pages. |
| `Gemfile` | Build | GitHub Pages-compatible Ruby dependencies. |
| `requirements-publications.txt` | Build | Python dependencies for generation and tests. |
| `Makefile` | Build | Local maintenance commands. |

## Jekyll content collections

### `_people/`

One Markdown file per current or former lab member. The front matter is the source of truth for the person’s Michigan `umid`, membership categories, lab roles, education, links, current position, and profile image. See [PEOPLE.md](PEOPLE.md).

### `_posts/`

Lab Life posts, grouped in year directories for maintainability. Jekyll uses the filename and front-matter date to create the public URL. See [NEWS_POSTS.md](NEWS_POSTS.md).

### `_jobs/`

Job announcements. Only records with `publish: true` appear on the Jobs page. See [JOBS.md](JOBS.md).

### `_papers/`

Generated publication records. Each filename is the stable BibTeX key, for example `_papers/VanDeynze2025HMMSTR.yml`. These files are committed because GitHub Pages and member pages consume them, but they must be regenerated rather than edited. See [PUBLICATIONS.md](PUBLICATIONS.md).

## Publication sources

| Path | Ownership | Purpose |
|---|---|---|
| `bibliography/publications.bib` | Authored | Definitive bibliographic citation data. |
| `publication_metadata/*.yml` | Authored | Website-only metadata, including member `umid` relationships, featured summaries, and supplemental links. |
| `scripts/publication_tools.py` | Code | BibTeX parser, validation, person matching, and record construction. |
| `scripts/build_publications.py` | Code | Generates `_papers/*.yml` and `pub.bib`; validates stale or obsolete output. |
| `scripts/scaffold_publication_metadata.py` | Code | Creates a new sidecar template for an existing BibTeX key. |

## Curriculum vitae

| Path | Ownership | Purpose |
|---|---|---|
| `cv/cv.tex` | Authored | CV sections other than the generated publication and patent lists. |
| `cv/patents.bib` | Authored | Patent records not represented in the website publication bibliography. |
| `cv/generated/publications.tex` | Generated | Full publication list with website-derived author highlighting. |
| `cv/generated/patents.tex` | Generated | Patent list included by `cv/cv.tex`. |
| `scripts/cv_tools.py` | Code | CV citation formatting and member highlighting built on the publication pipeline. |
| `scripts/build_cv.py` | Code | Generates CV TeX inputs and optionally compiles `assets/ABoyle_CV.pdf`. |
| `assets/ABoyle_CV.pdf` | Generated | Public CV linked from the People section. |

See [CV.md](CV.md).

## Presentation files

### `_layouts/`

- `default.html`: shared shell for normal pages.
- `member.html`: individual people profile.
- `post.html`: individual Lab Life story.

### `_includes/`

- `header.html`: document head, CSS, analytics, and navigation script.
- `nav.html`: lab and university marks plus desktop/mobile navigation.
- `footer.html`: compact institutional footer.
- `tracking.html`: Google Analytics configuration.
- `person_card.html`: reusable People-page card.
- `publication_authors.html`: full publication byline.
- `publication_citation.html`: complete or compact publication record.
- `publication_featured.html`: featured-publication card.
- `publications_page.html`: full Publications page.

### `css/`

- `main_style.css`: site-wide layout and component styles.
- `mobile_navigation.css`: only the responsive navigation behavior.
- `academicons.css`: minimal local Academic Icons subset used by member profiles.

### `assets/js/`

- `site-navigation.js`: accessible mobile-menu interaction. The site has no publication search or sorting JavaScript.

## Assets

| Directory | Purpose |
|---|---|
| `assets/images/` | Primary-page graphics, logos, and featured paper screenshots. |
| `assets/people/` | Profile photographs and placeholder image. |
| `assets/news_graphics/` | Lab Life teasers, event photographs, and legacy post galleries. |
| `assets/job_PDFs/` | PDFs linked by active job records. |
| `pubs/` | Local publication PDFs linked from BibTeX or metadata. |
| `fonts/` | Local Academic Icons WOFF font. |

Large Lab Life and publication archives are retained when a post, public URL, or download may still refer to them. Do not remove media solely because a literal path is not present in a template; some older Lab Life galleries discover files dynamically.

## Tests and automation

- `tests/test_publication_tools.py`: parser, metadata, generated schema, and reproducibility.
- `tests/test_cv_tools.py`: CV generation, author highlighting, TeX source, PDF output, and legacy-build removal.
- `tests/test_people_data.py`: profile identities, dates, roles, and assets.
- `tests/test_news_data.py`: Lab Life metadata and linked records.
- `tests/test_site_structure.py`: layouts, includes, CSS, dependencies, and repository shape.
- `tests/test_workflow.py`: GitHub Actions generation and deployment contract.
- `.github/workflows/site.yml`: publication and CV regeneration, validation, Jekyll build, and Pages deployment.
