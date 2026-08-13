# News posts

The News index is generated from Markdown files in `_posts/`, and each story uses `_layouts/post.html`. The current repository contains year subdirectories only for organization; Jekyll still derives the public URL from the filename and front-matter date.

## Standard front matter

```yaml
---
layout: post
published: true
title: Boyle Lab receives NINDS R01 award!
date: 2026-06-12
external-url: https://reporter.nih.gov/project-details/11363610
teaser: 2026/NINDS_R01_NUMT.png
categories:
  - Grants
---
```

Required fields are `layout`, `published`, `title`, `date`, `external-url`, `teaser`, and `categories`. Use `published: false` to retain a draft in the repository without placing it on the site.

`teaser` is resolved beneath `/assets/news_graphics/` unless it is already an absolute path or external URL. The same image becomes the default story hero.

## Editorial hero fields

```yaml
summary: >-
  A one- or two-sentence standfirst displayed below the title.

hero-image: 2026/high-resolution-image.png
hero-fit: contain        # contain or cover
hero-alt: Description of the lead image
hero-caption: Optional image credit or caption
hide-hero: false
cta-label: View project in NIH RePORTER
```

`Papers`, `Grants`, and `Awards` default to `contain`; other categories default to `cover`. A relative hero path is resolved under `/assets/news_graphics/`.

The layout also accepts underscore spellings (`hero_image`, `hero_fit`, and so forth) for compatibility, but new records should use the hyphenated forms shown above.

## Related publication

Use the permanent BibTeX key:

```yaml
related-publication: McDonald2021Cas9MobileElements
```

The story then displays the generated citation, full author list, and available article, DOI, PDF, PubMed, code, data, news, and BibTeX links. The key must exist in `_papers`.

All paper announcements should include `related-publication` when the matching paper exists in the bibliography.

## Related Boyle Lab members

Use Michigan `umid` values:

```yaml
people:
  - kvandeyn
  - crmumm
```

The story renders linked profile cards. Include lab members explicitly named or central to the announcement; do not use this field for external collaborators.

## Grant or award information

```yaml
award:
  agency: National Institute of Neurological Disorders and Stroke
  mechanism: R01 NS145291
  project: Characterization and functional impact of somatic numtogenesis in the human cortex
  collaborators:
    - Ryan Mills
```

`agency`, `mechanism`, and `project` are required when `award` is present. `collaborators` is optional and should contain external collaborators as display names. When `external-url` is present, the action link appears inside the award panel.

## Curated gallery

```yaml
gallery:
  - src: 2026/event/photo-01.jpg
    alt: Lab members attending the event
    caption: Optional caption
  - src: 2026/event/photo-02.jpg
    alt: Poster presentation
```

Relative gallery paths resolve under `/assets/news_graphics/`. Existing posts that generate galleries through Markdown or HTML remain supported; direct child image collections in the article body receive a responsive grid and images are centered with a maximum height.

## Automatic story elements

Every story receives:

- A News/category breadcrumb.
- Category and publication date.
- Left-aligned title and maize divider.
- Optional hero image and caption.
- Structured award, publication, people, and gallery sections when supplied.
- Previous story, All News, and next story navigation.
- Up to three recent posts from the same primary category.

The first value in `categories` is the primary category used in the breadcrumb, hero default, and related-story selection.

## News index and homepage

`news/index.html` uses `jekyll-paginate` with eight posts per page. The homepage lists the five newest posts and samples one image-bearing Events or Conferences post from the prior year at build time.
