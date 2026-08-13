# Job postings

Job records are stored in `_jobs/` and rendered by `jobs.html`.

## Front matter

```yaml
---
publish: true
title: Postdoctoral Associate in Computational Genomics
pdf: 2026-postdoctoral-position.pdf
---

Position description in Markdown or HTML.
```

- `publish`: Boolean. Only `true` records appear on the Jobs page.
- `title`: Required display title.
- `pdf`: Optional filename in `assets/job_PDFs/`.
- Body: Full position description. Existing records use HTML; Markdown is preferred for new postings.

The collection does not generate a separate page for each record. `jobs.html` places the body directly inside an opportunity card and adds a PDF action when supplied.

## Adding an opening

1. Create `_jobs/YYYY-MM-DD-short-name.md`.
2. Add the front matter above and write the description.
3. If needed, place a PDF in `assets/job_PDFs/` and set `pdf` to the filename.
4. Set `publish: true`.
5. Run `make check` and build the site.

## Closing an opening

Change only:

```yaml
publish: false
```

Retaining the file preserves the historical description without displaying it. Remove a PDF only after confirming that no active record or public link still uses it.
