# Boyle Lab news-post layout

The `_layouts/post.html` template provides the editorial layout for every item in `_posts`. Existing posts require no changes. The template continues to use the current `title`, `date`, `categories`, `teaser`, `external-url`, and Markdown body fields.

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

The teaser is displayed as the lead image. `Papers`, `Grants`, and `Awards` default to `contain`; other categories default to `cover`.

## Optional editorial fields

```yaml
summary: >-
  A one- or two-sentence standfirst that appears below the title.

hero-image: /assets/news_graphics/2026/high-resolution-image.png
hero-fit: contain        # contain or cover
hero-alt: Description of the lead image
hero-caption: Optional image credit or caption
hide-hero: false

cta-label: View project in NIH RePORTER
```

`hero-image` can point to a higher-resolution file while `teaser` remains the smaller News-index image. A relative `hero-image` or gallery path is resolved under `/assets/news_graphics/`.

## Related publication

Use the permanent BibTeX key from `_papers`:

```yaml
related-publication: McDonald2021Cas9MobileElements
```

The post will display the structured publication citation and its Article, DOI, PDF, PubMed, Code, Data, and BibTeX links when available. The separate external call-to-action is omitted because the publication card supplies the article link.

## Related lab members

Use Michigan `umid` values from `_people`:

```yaml
people:
  - apboyle
  - bmcbean
```

Each person is shown in a compact profile card linked to the member page.

## Grant or award information

```yaml
award:
  agency: National Institute of Neurological Disorders and Stroke
  mechanism: R01
  project: Characterization and functional impact of somatic numtogenesis in the human cortex
  collaborators:
    - Ryan Mills
```

When `external-url` is also present, its action appears inside this information panel.

## Curated image gallery

```yaml
gallery:
  - src: 2026/event/photo-01.jpg
    alt: Lab members at the event
    caption: Optional caption
  - src: 2026/event/photo-02.jpg
    alt: Poster presentation
```

Older posts that generate image galleries in their Markdown remain supported. Their direct child `<div>` image collections receive the same responsive two-column treatment.

## Automatic elements

Every post receives:

- A breadcrumb and category/date header.
- An optional lead image based on `hero-image` or `teaser`.
- Previous-story, All News, and next-story navigation.
- Up to three recent stories from the same primary category.
- Responsive typography, image treatment, and mobile layouts.
