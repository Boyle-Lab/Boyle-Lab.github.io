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
The People page header counts each published profile once. Profiles whose status includes `current` contribute to the current-member total; every other published profile contributes to the smaller lab-alumni total. Thus, a person with both `current` and `phd_alumni` remains part of the current-member count until `current` is removed.
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
## Current-role start dates

For a profile whose status includes `current`, the current role in **Boyle Lab history** displays `Since Month Year` whenever a start date can be determined.

To specify the start of the current appointment, add the optional `dates.current_role_start` field. Keep `dates.start` as the first date in the lab; it still controls the current-member list order. For example:

```yaml
dates:
  start: 2020-09-01
  current_role_start: 2023-08-01
```

This displays `Since August 2023` for the current role. Use an unquoted ISO date, as for the other date fields. This field describes the current appointment in the Boyle Lab, not the external `current_position` block below.

When `dates.current_role_start` is missing or blank, the layout uses the latest nonempty `end` date in `prior_lab_roles`. It compares calendar dates, so the order of the completed roles does not matter. The end date itself is used, without adding a day or month. No profile edits are required for this fallback.

For members with no prior roles, the layout continues to use `dates.start`. If prior roles exist but none has an end date, add `dates.current_role_start` or the missing prior-role end date; the layout retains `Current` rather than treating the initial lab-joining date as the start of a later role. Dates are not inferred from free-text `period` labels. Alumni entries and completed-role labels are unchanged.

The regression checks render the history section with the Liquid gem supplied by the site's existing bundle:

```bash
bundle exec ruby tests/test_member_role_dates.rb
```

## Current positions after the lab

Use a structured block:

```yaml
current_position:
  title: Bioinformatics Scientist
  organization: Example Company
  url: https://example.org/profile
  as_of: 2026-08-10
```
`title` is required when the block is present. `organization` is optional. For every published profile that is not marked `current`, include both a source `url` and an `as_of` date whenever a current position is listed. Prefer an official employer, university, hospital, or laboratory page; use a self-maintained professional page or LinkedIn only when no suitable institutional source exists. Do not add a position when a common name or conflicting evidence prevents a reliable identity match.
The member profile displays this information in a highlighted **Current position** panel immediately above **Boyle Lab history**. The source-by-source review completed on August 25, 2026 is recorded in [`ALUMNI_POSITION_AUDIT.md`](ALUMNI_POSITION_AUDIT.md); use that report as the baseline for later checks.
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
