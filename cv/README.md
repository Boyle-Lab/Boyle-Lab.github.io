# CV source directory

Edit `cv.tex` for CV content and `patents.bib` for patent records. Use `GRANT_AUDIT.md` to maintain the verified dates, titles, and investigator roles for Research Support. Follow the section, research-support, date, and role conventions documented in the repository-level `CV.md`. The publication bibliography and lab-member highlighting are supplied by the website repository.

Generated files under `generated/` are created by:

```bash
make cv-source
```

The deployed PDF is created by:

```bash
make cv
```

See the repository-level [CV.md](../CV.md) for the complete data model and deployment workflow.


## PDF build details

The PDF is compiled with LuaLaTeX. Major headings and hyperlinks use Michigan blue, the running header and total-page footer are generated in `cv.tex`, and `\cvsection` creates bookmarks for each major section. The source includes document metadata and enables LaTeX's tagged-PDF layer. See the repository-level [CV.md](../CV.md) for accessibility scope and validation notes.
