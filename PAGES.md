# Pages, layouts, and shared components

## Rendering model

Most primary pages use:

```yaml
---
title: Page title
layout: default
---
```

`_layouts/default.html` assembles the common shell in this order:

1. `_includes/header.html`
2. `_includes/nav.html`
3. Page content inside `#main-wrap .container`
4. `_includes/footer.html`

Individual people records use `_layouts/member.html`. News posts use `_layouts/post.html`. Both layouts include the same header, navigation, and footer directly.

## Primary pages

### Homepage: `index.html`

The homepage contains three sections:

- A concise “Exploring the Genome” introduction.
- “Our Work,” generated from the three newest records in `site.papers`.
- “News,” containing the five newest posts and one randomly sampled event or conference teaser from the preceding year.

The event image is selected at Jekyll build time. No browser JavaScript is used.

### Research: `research.html`

The Research page contains an overview and alternating illustrated research-program panels. Add a new program by copying a `<article class="research-program">` block and placing its image in `assets/images/`.

### People: `people.html`

The People page reads `_people`. A person may appear in more than one section because `status` is a list. Ph.D. alumni are ordered by the end date of the `Ph.D. student` entry in `prior_lab_roles`, newest first. See [PEOPLE.md](PEOPLE.md).

### Software: `software.html`

Software is maintained directly as card markup. Each card may contain a purpose statement and resource links such as website, source code, documentation, publication, or download.

### Publications: `publications.html`

This file intentionally remains a small wrapper around `_includes/publications_page.html`. The page uses generated `_papers` records, shows four curated featured papers, groups the full list by year, displays complete author lists, and loads live citation counts. See [PUBLICATIONS.md](PUBLICATIONS.md).

### News: `news/index.html`

The News index uses `jekyll-paginate` and displays eight posts per page. Individual stories use `_layouts/post.html`. See [NEWS_POSTS.md](NEWS_POSTS.md).

### Jobs: `jobs.html`

The page renders published `_jobs` records and an empty-state message when no opening is active. See [JOBS.md](JOBS.md).

### Contact: `contact.html`

The page contains office and wet-lab locations, maps, and building imagery. Edit the address and map links directly in this file.

### BibTeX browser: `pub_bib.html`

This page lists the embedded `bibtex` field from every generated paper and links to `/pub.bib`. Do not maintain a second bibliography here.

## Header and navigation

`_includes/header.html` owns document metadata and dependencies. `nav.html` owns the visible site header. The current navigation links are Home, Research, People, Software, Publications, Jobs, News, and Contact.

At widths of 720 px or less, `mobile_navigation.css` and `assets/js/site-navigation.js` replace the horizontal menu with an accessible Menu button and two-column link panel. Keep the `aria-controls`, `aria-expanded`, and `hidden` attributes when changing the button.

## Footer

`_includes/footer.html` is intentionally compact. It contains the lab identity, three university affiliation links, a generated copyright year, and Contact. Add only high-value links; the footer should not duplicate the entire primary navigation.

## Reusable includes

Use the existing includes rather than copying their markup:

```liquid
{% include person_card.html person=person %}
{% include publication_citation.html paper=paper compact=true %}
{% include publication_featured.html paper=paper %}
```

The publication citation accepts these principal parameters:

- `paper`: required generated publication record.
- `compact=true`: tighter member/news presentation.
- `member_id`: shows that member’s non-byline role, when present.
- `show_abstract=true`: allows an expandable abstract.
- `show_metrics=true`: renders a live citation badge when DOI or PMID exists.
- `show_consortium=true`: displays a Consortium badge if any `member_roles` value is `consortium`.

## Page style conventions

Primary pages use `.site-page`, `.site-page-header`, `.section-eyebrow`, `.section-heading`, `.site-action-links`, and component-specific classes. Avoid inline styles. Add component CSS to `main_style.css`; reserve `mobile_navigation.css` for navigation behavior only.
