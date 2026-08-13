# Boyle Lab website

This repository contains the source for [boylelab.org](https://boylelab.org), a Jekyll site deployed through GitHub Pages.

## Sources of truth

| Content | Authoritative source | Generated or rendered output |
|---|---|---|
| Publications | `bibliography/*.bib` and `publication_metadata/*.yml` | `_papers/*.yml` and `pub.bib` |
| People | `_people/*.md` | `/people/` and individual profiles |
| News | `_posts/<year>/*.md` | `/news/` and individual stories |
| Jobs | `_jobs/*.md` | `/jobs/` |
| Primary pages | Root HTML files and `news/index.html` | Public site pages |
| Shared presentation | `_layouts/`, `_includes/`, and `css/` | All rendered pages |

Do not edit files in `_papers/` or the root `pub.bib` by hand. They are generated from the BibTeX and sidecar sources.

## Common commands

```bash
python3 -m pip install -r requirements-publications.txt
bundle install
make publications       # regenerate _papers and pub.bib
make check              # verify generated files and run all tests
make build              # regenerate, test, and build _site
make serve              # local Jekyll server with live reload
```

The equivalent one-command production build is:

```bash
scripts/build_site.sh
```

## Documentation

- [SITE_STRUCTURE.md](SITE_STRUCTURE.md): repository map and file ownership.
- [PAGES.md](PAGES.md): primary pages, layouts, includes, navigation, and footer.
- [PEOPLE.md](PEOPLE.md): member-profile schema and role history.
- [PUBLICATIONS.md](PUBLICATIONS.md): BibTeX pipeline and publication sidecars.
- [NEWS_POSTS.md](NEWS_POSTS.md): news-post front matter and editorial components.
- [JOBS.md](JOBS.md): job-posting collection.
- [DEVELOPMENT.md](DEVELOPMENT.md): local development, testing, and deployment.
- [STYLES_AND_ASSETS.md](STYLES_AND_ASSETS.md): CSS and asset conventions.
- [CLEANUP.md](CLEANUP.md): removed legacy files and retention decisions.

## Automated deployment

`.github/workflows/site.yml` regenerates publications, runs the test suite, builds the Jekyll site, and deploys it to GitHub Pages. On a direct push, it commits changes to `_papers/` and `pub.bib` when the BibTeX or sidecar sources produce new output. Pull requests must include current generated files.
