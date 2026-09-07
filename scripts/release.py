"""Release validation and notes helpers for OrchAI."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER_TAG_PATTERN = re.compile(r"^v(?P<version>0\.\d+\.\d+)$")
COMMIT_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?: (?P<summary>.+)$"
)

SECTION_TITLES = {
    "feat": "Features",
    "fix": "Fixes",
    "test": "Tests",
    "ci": "CI",
    "docs": "Documentation",
    "refactor": "Refactors",
    "chore": "Maintenance",
}


@dataclass(frozen=True)
class CommitEntry:
    """One Git commit included in release notes."""

    short_hash: str
    subject: str


def project_version(root: Path = ROOT) -> str:
    """Read the canonical project version from pyproject.toml."""
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    if not isinstance(version, str):
        raise ValueError("pyproject.toml project.version must be a string")
    return version


def validate_release_tag(tag: str, version: str) -> None:
    """Validate the release tag format and ensure it matches the project version."""
    match = SEMVER_TAG_PATTERN.fullmatch(tag)
    if match is None:
        raise ValueError("Release tag must use the v0.x.y format, for example v0.1.11")
    if match.group("version") != version:
        raise ValueError(f"Release tag {tag} does not match project version {version}")


def run_git(args: list[str], root: Path = ROOT) -> str:
    """Run a Git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def previous_tag(root: Path = ROOT) -> str | None:
    """Return the most recent reachable version tag, when one exists."""
    try:
        tag = run_git(["describe", "--tags", "--abbrev=0"], root=root)
    except subprocess.CalledProcessError:
        return None
    return tag or None


def commit_entries(revision_range: str, root: Path = ROOT) -> list[CommitEntry]:
    """Read commit entries for a Git revision range."""
    output = run_git(["log", "--format=%h%x1f%s", revision_range], root=root)
    entries: list[CommitEntry] = []
    for line in output.splitlines():
        short_hash, separator, subject = line.partition("\x1f")
        if separator:
            entries.append(CommitEntry(short_hash=short_hash, subject=subject))
    return entries


def section_for_subject(subject: str) -> str:
    """Map a Conventional Commit subject to a release notes section."""
    match = COMMIT_PATTERN.fullmatch(subject)
    if match is None:
        return "Other Changes"
    if match.group("breaking"):
        return "Breaking Changes"
    return SECTION_TITLES.get(match.group("type"), "Other Changes")


def release_notes_markdown(
    *,
    tag: str,
    version: str,
    revision_range: str,
    entries: list[CommitEntry],
) -> str:
    """Build release notes Markdown for a validated tag and commit entries."""
    validate_release_tag(tag, version)

    grouped_entries: dict[str, list[CommitEntry]] = {}
    for entry in entries:
        grouped_entries.setdefault(section_for_subject(entry.subject), []).append(entry)

    lines = [
        f"# {tag}",
        "",
        f"Release notes for OrchAI {version}.",
        "",
        f"Revision range: `{revision_range}`",
    ]

    for section in [
        "Breaking Changes",
        "Features",
        "Fixes",
        "Tests",
        "CI",
        "Documentation",
        "Refactors",
        "Maintenance",
        "Other Changes",
    ]:
        section_entries = grouped_entries.get(section, [])
        if not section_entries:
            continue
        lines.extend(["", f"## {section}", ""])
        lines.extend(f"- {entry.subject} ({entry.short_hash})" for entry in section_entries)

    if not entries:
        lines.extend(["", "No commits found for this release range."])

    return "\n".join(lines) + "\n"


def generate_release_notes(tag: str, output_path: Path, root: Path = ROOT) -> None:
    """Generate release notes for the current repository state."""
    version = project_version(root)
    validate_release_tag(tag, version)
    previous = previous_tag(root)
    revision_range = f"{previous}..HEAD" if previous else "HEAD"
    notes = release_notes_markdown(
        tag=tag,
        version=version,
        revision_range=revision_range,
        entries=commit_entries(revision_range, root=root),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(notes, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Build the release automation CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-tag")
    validate_parser.add_argument("--tag", required=True)

    notes_parser = subparsers.add_parser("generate-notes")
    notes_parser.add_argument("--tag", required=True)
    notes_parser.add_argument(
        "--output",
        type=Path,
        default=Path("runtime/release-notes.md"),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run release automation commands."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        version = project_version()
        if args.command == "validate-tag":
            validate_release_tag(args.tag, version)
            print(f"Release tag {args.tag} matches OrchAI {version}.")
            return 0
        if args.command == "generate-notes":
            generate_release_notes(args.tag, args.output)
            print(f"Release notes written to {args.output}.")
            return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"release automation failed: {error}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
