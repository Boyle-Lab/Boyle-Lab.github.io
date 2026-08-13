#!/usr/bin/env python3
"""Generate and optionally compile Alan Boyle's CV from website source data."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from cv_tools import expected_cv_outputs
from publication_tools import BuildMessage, PublicationError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Website repository root",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate generated CV source without modifying files",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Compile cv/cv.tex and write assets/ABoyle_CV.pdf",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat publication/member mapping warnings as errors",
    )
    return parser.parse_args()


def print_messages(messages: list[BuildMessage]) -> int:
    warnings = 0
    for message in messages:
        stream = sys.stderr if message.level in {"warning", "error"} else sys.stdout
        print(f"{message.level.upper()}: {message.message}", file=stream)
        if message.level == "warning":
            warnings += 1
    return warnings


def check_outputs(root: Path, outputs: dict[Path, str]) -> list[str]:
    problems: list[str] = []
    for path, expected in outputs.items():
        if not path.exists():
            problems.append(f"missing generated CV file: {path.relative_to(root)}")
        elif path.read_text(encoding="utf-8") != expected:
            problems.append(f"stale generated CV file: {path.relative_to(root)}")
    return problems


def write_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _source_date_epoch(root: Path) -> str:
    """Return a stable build timestamp tied to authored CV inputs.

    Generated-file-only commits must not alter the PDF metadata or ``\\today``.
    In a clean Git checkout, use the most recent commit that changed an authored
    CV input.  For an uncommitted local edit or an extracted archive without Git
    history, use the newest source-file modification time instead.
    """
    configured = os.environ.get("SOURCE_DATE_EPOCH")
    if configured:
        return configured

    relative_sources = [
        "cv/cv.tex",
        "bibliography/publications.bib",
        "cv/patents.bib",
        "publication_metadata",
        "_people",
    ]
    source_files = [
        root / "cv" / "cv.tex",
        root / "bibliography" / "publications.bib",
        root / "cv" / "patents.bib",
        *(root / "publication_metadata").glob("*.yml"),
        *(root / "publication_metadata").glob("*.yaml"),
        *(root / "_people").glob("*.md"),
    ]

    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", *relative_sources],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not dirty:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ct", "--", *relative_sources],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            value = result.stdout.strip()
            if value.isdigit():
                return value
    except (OSError, subprocess.CalledProcessError):
        pass

    timestamps = [int(path.stat().st_mtime) for path in source_files if path.exists()]
    return str(max(timestamps) if timestamps else 0)


def compile_cv(root: Path) -> Path:
    xelatex = shutil.which("xelatex")
    if not xelatex:
        raise PublicationError(
            "xelatex is required to compile the CV. Install TeX Live with XeLaTeX, "
            "or run scripts/build_cv.py without --compile to generate only the TeX inputs."
        )

    cv_dir = root / "cv"
    build_dir = cv_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("SOURCE_DATE_EPOCH", _source_date_epoch(root))
    env.setdefault("FORCE_SOURCE_DATE", "1")

    command = [
        xelatex,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-output-directory=build",
        "cv.tex",
    ]
    for _ in range(2):
        result = subprocess.run(
            command,
            cwd=cv_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            log = (result.stdout + "\n" + result.stderr).strip()
            tail = "\n".join(log.splitlines()[-80:])
            raise PublicationError(f"XeLaTeX failed while building the CV:\n{tail}")

    built_pdf = build_dir / "cv.pdf"
    if not built_pdf.exists():
        raise PublicationError("XeLaTeX completed without producing cv/build/cv.pdf")
    destination = root / "assets" / "ABoyle_CV.pdf"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built_pdf, destination)
    return destination


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        outputs, messages, publication_count = expected_cv_outputs(root)
        warning_count = print_messages(messages)
        if args.strict and warning_count:
            print(f"ERROR: strict mode rejected {warning_count} warning(s)", file=sys.stderr)
            return 1

        if args.check:
            problems = check_outputs(root, outputs)
            for problem in problems:
                print(f"ERROR: {problem}", file=sys.stderr)
            if problems:
                print(
                    "Generated CV source is not current. Run: python scripts/build_cv.py",
                    file=sys.stderr,
                )
                return 1
            print(f"Validated generated CV source for {publication_count} publications.")
        else:
            write_outputs(outputs)
            print(f"Generated CV source for {publication_count} publications.")

        if args.compile:
            destination = compile_cv(root)
            print(f"Built {destination.relative_to(root)}")
        return 0
    except PublicationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
