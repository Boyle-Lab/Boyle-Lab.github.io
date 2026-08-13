# Development, testing, and deployment

## Prerequisites

- Python 3.11 or newer.
- Ruby compatible with the current `github-pages` gem.
- Bundler.
- Git.

Install dependencies:

```bash
python3 -m pip install --requirement requirements-publications.txt
bundle install
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
make test
```

Runs the full Python test suite.

```bash
make check
```

Runs the publication reproducibility check followed by all tests. Use this before every commit.

```bash
make build
```

Regenerates publications, runs tests, and creates the production site in `_site/`.

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
- `test_people_data.py`: unique `umid` values, list-valued statuses, YAML date types, role history, assets, alumni sorting, and current positions.
- `test_news_data.py`: required front matter, teaser assets, member links, publication links, award metadata, and layout support.
- `test_site_structure.py`: valid includes/layouts, current dependencies, CSS parsing and use, primary navigation, and required documentation.
- `test_workflow.py`: generation, validation, auto-commit, build, and Pages deployment steps.

Add a regression test whenever a content mistake causes a build failure. For example, date-type tests prevent Liquid from sorting a mixture of YAML dates and quoted strings.

## GitHub Actions workflow

`.github/workflows/site.yml` runs on pushes and pull requests targeting `main` or `master`, and can be started manually.

The build job:

1. Checks out full Git history.
2. Installs Python dependencies.
3. Regenerates publication output in strict mode.
4. Runs all tests.
5. On pull requests, fails if `_papers/` or `pub.bib` differ from committed files.
6. On direct pushes, commits changed generated publication files with the GitHub Actions bot.
7. Builds Jekyll and uploads the Pages artifact.

The deploy job runs only outside pull requests and publishes the artifact to the `github-pages` environment.

In repository **Settings → Pages**, set the publishing source to **GitHub Actions**. The workflow supports either `main` or `master` as the default branch.

A commit created by `GITHUB_TOKEN` does not need a second workflow run: the active run builds and deploys from the regenerated working tree after committing it.

## Editing publication sources in GitHub

When `bibliography/publications.bib` changes directly on GitHub, the workflow regenerates the website records and `pub.bib`, commits those outputs, and deploys the generated site. A new BibTeX key still requires a matching `publication_metadata/*.yml` sidecar; otherwise strict generation fails with a clear missing-sidecar message.

## Troubleshooting

### “Generated publication files are not current”

Run:

```bash
make publications
```

Commit `_papers/` and `pub.bib` with the source changes.

### Liquid comparison errors on the People page

Confirm that `dates.start`, `dates.end`, and dated `prior_lab_roles` values are unquoted ISO YAML dates.

### A member does not appear on a publication

Confirm the `umid` in the sidecar, then add `author_member_map` for a historical byline or `member_roles` for consortium/non-byline participation.

### Jekyll pagination is missing

Run through Bundler and confirm `_config.yml` contains `jekyll-paginate` under `plugins`.
