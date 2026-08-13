# Development, testing, and deployment

## Prerequisites

- Python 3.11 or newer.
- Ruby compatible with the current `github-pages` gem.
- Bundler.
- Git.
- XeLaTeX and Liberation Sans when compiling the CV locally.

Install dependencies:

```bash
python3 -m pip install --requirement requirements-publications.txt
bundle install
# Debian/Ubuntu only, for CV compilation:
sudo apt-get install fonts-liberation2 texlive-latex-extra texlive-xetex
```

The Python requirements support the publication generator and repository tests. The Gemfile uses the GitHub Pages dependency bundle so local Jekyll behavior remains close to production.

## Maintenance commands

```bash
make publications
```

Regenerates `_papers/*.yml` and `pub.bib` from the authoritative sources. Strict mode rejects unmatched member mappings.

```bash
make publications-check
```

Reconstructs expected output in memory and fails if committed generated files are stale, missing, or obsolete.

```bash
make cv-source
```

Regenerates the CV publication and patent TeX files without compiling the PDF.

```bash
make cv
```

Regenerates publication data, compiles the CV, and writes `assets/ABoyle_CV.pdf`.

```bash
make cv-check
```

Fails when committed `cv/generated/*.tex` files are stale.

```bash
make test
```

Runs the full Python test suite.

```bash
make check
```

Runs the publication and CV reproducibility checks followed by all tests. Use this before every commit.

```bash
make build
```

Regenerates publications, compiles the CV, runs tests, and creates the production site in `_site/`.

```bash
make serve
```

Regenerates publications and starts a local Jekyll server with live reload.

```bash
scripts/build_site.sh
```

Runs the same generate-test-build sequence with shell error handling and is useful in other CI systems.

## Test suite

- `test_publication_tools.py`: BibTeX parsing, member matching, generated schema, stable filenames, featured records, citation metrics, and deterministic output.
- `test_cv_tools.py`: CV source generation, member highlighting, legacy dependency removal, and PDF presence.
- `test_people_data.py`: unique `umid` values, list-valued statuses, YAML date types, role history, assets, alumni sorting, and current positions.
- `test_news_data.py`: required front matter, teaser assets, member links, publication links, award metadata, and layout support.
- `test_site_structure.py`: valid includes/layouts, current dependencies, CSS parsing and use, primary navigation, and required documentation.
- `test_workflow.py`: generation, validation, auto-commit, build, and Pages deployment steps.

Add a regression test whenever a content mistake causes a build failure. For example, date-type tests prevent Liquid from sorting a mixture of YAML dates and quoted strings.

## GitHub Actions workflow

`.github/workflows/site.yml` runs automatically only when `bibliography/publications.bib` changes in a push or pull request targeting `main` or `master`. It can also be started manually with **Run workflow** in GitHub Actions.

The build job:

1. Checks out full Git history.
2. Installs Python dependencies and XeLaTeX.
3. Regenerates publication output in strict mode.
4. Generates and compiles the CV from the same publication and people data.
5. Runs all tests.
6. On pull requests, fails if generated publication records or generated CV TeX differ from committed files; the PDF is still compiled so XeLaTeX errors are caught.
7. On direct pushes, commits changed publication records, generated CV TeX, and the canonical CV PDF with the GitHub Actions bot.
8. Builds Jekyll and uploads the Pages artifact.

The deploy job runs only outside pull requests and publishes the artifact to the `github-pages` environment.

In repository **Settings → Pages**, set the publishing source to **GitHub Actions**. The workflow supports either `main` or `master` as the default branch.

Because the workflow is path-limited, changes that do not modify `bibliography/publications.bib` do not start an automatic Pages deployment. After a news, people, CSS, layout, or other site-only update, start this workflow manually unless a separate general site-deployment workflow is configured.

A commit created by `GITHUB_TOKEN` does not need a second workflow run: the active run builds and deploys from the regenerated working tree after committing it.

## Editing publication sources in GitHub

When `bibliography/publications.bib` changes directly on GitHub, the workflow regenerates the website records, `pub.bib`, and CV, commits those outputs, and deploys the generated site. A new BibTeX key still requires a matching `publication_metadata/*.yml` sidecar; otherwise strict generation fails with a clear missing-sidecar message.

## Troubleshooting

### “Generated publication files are not current”

Run:

```bash
make publications
```

Run `make publications` and `make cv-source`, then commit `_papers/`, `pub.bib`, and `cv/generated/`. Running `make cv` also refreshes the local PDF; the direct-push workflow produces and commits the canonical deployed PDF.

### Liquid comparison errors on the People page

Confirm that `dates.start`, `dates.end`, and dated `prior_lab_roles` values are unquoted ISO YAML dates.

### A member does not appear on a publication

Confirm the `umid` in the sidecar, then add `author_member_map` for a historical byline or `member_roles` for consortium/non-byline participation.

### Jekyll pagination is missing

Run through Bundler and confirm `_config.yml` contains `jekyll-paginate` under `plugins`.

### XeLaTeX is unavailable

Run `make cv-source` to generate the CV publication data without compiling. To create the PDF, install `fonts-liberation2`, `texlive-latex-extra`, and `texlive-xetex`, then run `make cv`.
