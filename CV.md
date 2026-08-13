# Curriculum vitae build

Alan Boyle's CV is built inside the website repository so its publication list cannot drift from the Publications page.

## Sources and outputs

```text
cv/cv.tex
        +
bibliography/publications.bib
        +
publication_metadata/*.yml
        +
_people/*.md
        +
cv/patents.bib
        |
        v
scripts/build_cv.py
        |
        +--> cv/generated/publications.tex
        +--> cv/generated/patents.tex
        +--> assets/ABoyle_CV.pdf
```

### Authored files

- `cv/cv.tex`: all CV sections except publications and patents.
- `cv/patents.bib`: patent citation data, which are not part of the website publication bibliography.
- `bibliography/publications.bib`: definitive publication citation data shared with the website.
- `publication_metadata/*.yml`: publication-to-member relationships and publication-specific author mappings.
- `_people/*.md`: canonical member identities keyed by Michigan `umid`.

### Generated files

- `cv/generated/publications.tex`: reverse-chronological publication list included by `cv/cv.tex`; labels count down from the total number of publications so the oldest publication remains number 1.
- `cv/generated/patents.tex`: numbered patent list included by `cv/cv.tex`.
- `assets/ABoyle_CV.pdf`: PDF linked from Alan Boyle's profile and deployed with the website.

Do not edit files under `cv/generated/` by hand. They are replaced by the Python generator.

## CV organization and formatting conventions

The authored CV separates faculty appointments from institutional memberships and places nonacademic work under `Other Professional Experience`. Research support is divided by active/completed status and by the role held on the award. Active PI and Multi-PI awards may include one concise sentence describing the work; co-investigator, consultant, and completed awards list the award, sponsor, project title, and role without repeated project narratives.

Professional service uses five subsections:

```text
Institutional and Consortium Leadership
Editorial and Program Committee Service
Grant Review
Manuscript Review
Professional Memberships
```

Use these conventions when editing `cv/cv.tex`:

- Use `present`, not `current`, for open date ranges.
- Show a one-year appointment as `2025`, not `2025--2025`.
- Use `PI`, `Co-PI`, `Multi-PI`, and `Co-I` consistently.
- Use compact semester codes for recurring courses (`F` = fall, `W` = winter, `S` = summer), preserving the original course history format.
- Preserve official project and thesis titles, while correcting clear typographical errors.
- Use `DCMB` consistently for the Department of Computational Medicine and Bioinformatics in service entries; use the full department name in academic appointments.

The source uses the `needspace` package and nonbreaking long-table rows to keep a research-support heading or award from being stranded across pages.

## PDF navigation, appearance, and accessibility

The compiled CV uses Michigan blue (`#00274C`) for major section headings and hyperlinks while retaining black body text. The blue is intentionally dark so links remain legible when the PDF is printed in grayscale.

Every page uses the running header `Updated August 2026` and `Alan P. Boyle | Curriculum Vitae`, with a dynamic `Page N of M` footer. Major sections are generated with `\cvsection`, which keeps headings unnumbered in the printed CV while adding them to the PDF outline. Publications and patents use the same command through `scripts/cv_tools.py`.

The source also supplies PDF title, author, subject, and keyword metadata. LuaLaTeX enables the current LaTeX tagging layer and declares English (`en-US`) and PDF/UA-1 metadata. The resulting PDF contains a structure tree and is reported as tagged by standard PDF inspection tools. This automated tagging improves screen-reader navigation, but it should not be described as independently certified PDF/UA conformance without a dedicated accessibility audit.

Grant dates, titles, award identifiers, and investigator roles are documented in `cv/GRANT_AUDIT.md`. Update that audit whenever the Research Support section changes; distinguish publicly verified award facts from non-PI roles retained from the institutional CV.

The PDF build uses `SOURCE_DATE_EPOCH`. In a clean Git checkout, the default timestamp is the most recent commit that changed an authored CV input (`cv/cv.tex`, the publication bibliography and sidecars, `_people`, or `cv/patents.bib`). A bot commit that changes only generated files therefore does not alter the CV date or binary output on the next run.

## Author highlighting

The CV does not contain a hard-coded list of lab-member names. For each publication, the generator uses the same `members`, `author_member_map`, and `member_roles` metadata used by the website.

- Alan Boyle (`umid: apboyle`) is printed in bold.
- Other Boyle Lab members attached to the byline are underlined.
- Co-first and co-senior markers come from `*` and `\dag` markers in the BibTeX author field.
- Consortium or other non-byline roles associate a paper with a member profile but do not insert or highlight a person who is absent from the byline.

A historical publication name belongs in that publication's sidecar:

```yaml
bibkey: Mumm2023OnRamp
members:
  - melyssae
  - apboyle
author_member_map:
  melyssae: "Drexel, Melissa L"
```

The same mapping then controls both the website link and CV underline.

## Commands

Generate the two included TeX files without compiling the PDF:

```bash
make cv-source
```

Generate the publication files and compile the PDF:

```bash
make cv
```

Check that committed generated TeX files are current:

```bash
make cv-check
```

Run all publication, CV, content, and workflow checks:

```bash
make check
```

Direct equivalents are:

```bash
python3 scripts/build_cv.py --strict
python3 scripts/build_cv.py --strict --compile
python3 scripts/build_cv.py --check --strict
```

## Local prerequisites

The source generator requires Python and the packages in `requirements-publications.txt`. PDF compilation requires LuaLaTeX with the standard LaTeX-extra packages and Liberation Sans. LuaLaTeX is used because the tagged-PDF build is not reliable with the prior XeLaTeX path.

On Ubuntu or Debian:

```bash
sudo apt-get install fonts-liberation2 texlive-latex-extra texlive-luatex
```

The GitHub Actions workflow installs these packages automatically.

## GitHub deployment

The site workflow runs automatically when `bibliography/publications.bib` changes and can also be started manually. It regenerates the website publication records, generates and compiles the CV, runs all tests, commits generated publication/CV outputs after a direct push, builds Jekyll, and deploys the site. Pull requests compare the deterministic YAML, BibTeX, and generated TeX outputs; they still compile the PDF to detect LuaLaTeX or tagging failures without requiring the binary PDF to match local build-date metadata.

Because the automatic trigger is intentionally limited to `bibliography/publications.bib`, use **Run workflow** after changing only `cv/cv.tex`, `cv/patents.bib`, `_people`, or `publication_metadata` if an immediate CV rebuild and deployment is needed.

## Legacy CV repository

The integrated build replaces these former CV-repository components:

- `apb.bib`, which duplicated the website bibliography.
- `bold_bib4tex.pl`, which hard-coded member names.
- `mod_bib_html.pl` and the BibTeX2HTML binaries, which generated the former website bibliography.
- `bib_to_yaml.py`, which did not create the current publication schema.
- The custom publication `.bst` dependency and multibib publication build.

The old repository may be retained as an archive, but it is no longer required to build or deploy the CV.
