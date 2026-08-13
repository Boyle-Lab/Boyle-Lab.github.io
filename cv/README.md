# CV source directory

Edit `cv.tex` for CV content and `patents.bib` for patent records. The publication bibliography and lab-member highlighting are supplied by the website repository.

Generated files under `generated/` are created by:

```bash
make cv-source
```

The deployed PDF is created by:

```bash
make cv
```

See the repository-level [CV.md](../CV.md) for the complete data model and deployment workflow.
