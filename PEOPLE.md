# People records

Each person has one canonical file in `_people/`. The Michigan `umid` is the permanent identity key used by publications and news posts.

## Complete example

```yaml
---
layout: member
publish: true
status:
  - current
  - phd_alumni
name: Kinsey Van Deynze, Ph.D.
umid: kvandeyn
position: Postdoctoral Scholar
title: Postdoctoral Scholar
picture: Kinsey_Van_Deynze.png

dates:
  start: 2021-01-19

prior_lab_roles:
  - position: Bioinformatics Ph.D. student
    start: 2021-01-19
    end: 2025-10-06

current_position:
  title: Senior Scientist
  organization: Example Organization
  url: https://example.org/profile
  as_of: 2026-08-10

previous_training:
  - type: B.S.
    info: University of California, San Diego
  - type: Ph.D.
    info: University of Michigan

social:
  email: person@umich.edu
  github: username
  google-scholar: ScholarIdentifier
  orcid: 0000-0000-0000-0000
  linked-in: profile-slug
  website: https://example.org

theme_areas:
  - Long-read sequencing
  - Tandem repeats

awards:
  - Example fellowship
---
Biography in Markdown.
```

## Required fields

- `layout: member`
- `publish`: Boolean. Unpublished records remain in the collection but are omitted from lists.
- `status`: nonempty YAML list.
- `name`: displayed name.
- `umid`: unique Michigan `umid` and cross-record identifier.
- `position`: broad lab role used by cards.
- `dates.start`: first date in the lab.

Dates must be unquoted ISO dates:

```yaml
dates:
  start: 2021-01-19
  end: 2025-10-06
```

Do not use quoted date strings. Mixed YAML date and string types can make Liquid sorting fail.

## Multiple statuses

A person may belong to several sections:

```yaml
status:
  - current
  - phd_alumni
```

Supported values are:

- `current`
- `phd_alumni`
- `alumni`
- `rotation`

For example, a former Boyle Lab Ph.D. student who remains as a postdoctoral scholar should use both `current` and `phd_alumni`.

## Lab role history

Use only `prior_lab_roles` for completed appointments:

```yaml
prior_lab_roles:
  - position: Bioinformatics Ph.D. student
    start: 2017-07-17
    end: 2023-03-29
  - position: Postdoctoral Scholar
    start: 2023-05-01
    end: 2025-05-23
```

The old fields `phd_start`, `phd_end`, `pd_start`, `pd_end`, `ms_start`, and `ms_end` are not supported.

Every published profile with `phd_alumni` must have exactly one completed role whose `position` contains `Ph.D. student`. `people.html` reads that role’s `end` date to order the alumni section.

## Current positions after the lab

Use a structured block:

```yaml
current_position:
  title: Bioinformatics Scientist
  organization: Example Company
  url: https://example.org/profile
  as_of: 2026-08-10
```

`title` is required when the block is present. `organization`, `url`, and `as_of` are optional. The member profile and alumni card display this information.

## Images and links

Place profile photographs in `assets/people/` and store only the filename:

```yaml
picture: Person_Name.jpg
```

Social values may be either identifiers or complete URLs. The member layout expands identifiers for GitHub, Google Scholar, ORCID, LinkedIn, and Twitter.

## Publication relationships

Do not store publication lists or author aliases in `_people`. A publication sidecar associates the paper with the person by `umid`:

```yaml
members:
  - kvandeyn
```

If a historical byline differs from the current profile name, add `author_member_map` to that publication’s sidecar. See [PUBLICATIONS.md](PUBLICATIONS.md).
