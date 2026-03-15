"""Spec decomposer — splits a monolithic PRD into feature-scoped specs/features/ tree.

Architecture reference: specs/features/spec-decomposer/arch.md
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from sdd_server.infrastructure.filesystem import FileSystemClient
from sdd_server.models.base import SDDBaseModel

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FEATURES = 50

_AC_PATTERN = re.compile(r"\bAC-\d+\b")
_FEATURE_KEYWORD_RE = re.compile(r"(feature|section|\b\d+\.\d*\b)", re.IGNORECASE)
_USER_STORY_RE = re.compile(r"user story", re.IGNORECASE)

_ROLE_CHECKLIST = """\
- [ ] **Spec Linter** — `goose run --recipe specs/recipes/spec-linter.yaml`
- [ ] **Architect** — `goose run --recipe specs/recipes/architect.yaml`
- [ ] **UI/UX Designer** — `goose run --recipe specs/recipes/ui-designer.yaml`
- [ ] **Interface Designer** — `goose run --recipe specs/recipes/interface-designer.yaml`
- [ ] **Security Analyst** — `goose run --recipe specs/recipes/security-analyst.yaml`
- [ ] **Edge Case Analyst** — `goose run --recipe specs/recipes/edge-case-analyst.yaml`
- [ ] **Senior Developer** — `goose run --recipe specs/recipes/senior-developer.yaml`
- [ ] **QA Engineer** — `goose run --recipe specs/recipes/qa-engineer.yaml`
- [ ] **Tech Writer** — `goose run --recipe specs/recipes/tech-writer.yaml`
- [ ] **DevOps Engineer** — `goose run --recipe specs/recipes/devops-engineer.yaml`
- [ ] **Product Owner** — `goose run --recipe specs/recipes/product-owner.yaml`"""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class FeatureBoundary(SDDBaseModel):
    """A detected feature boundary within a PRD."""

    slug: str
    title: str
    acs: list[str] = Field(default_factory=list)
    content_blocks: list[str] = Field(default_factory=list)
    source_line_start: int = 0
    source_line_end: int = 0


class DecompositionResult(SDDBaseModel):
    """Result of a decomposition run."""

    features: list[FeatureBoundary] = Field(default_factory=list)
    skipped: list[dict[str, str]] = Field(default_factory=list)
    unassigned_acs: list[str] = Field(default_factory=list)
    coverage_pct: float = 0.0
    files_created: list[str] = Field(default_factory=list)
    dry_run: bool = False


# ---------------------------------------------------------------------------
# SpecDecomposer engine
# ---------------------------------------------------------------------------


class SpecDecomposer:
    """Decomposes a monolithic specs/prd.md into feature-scoped sub-specs."""

    def __init__(self, project_root: Path, fs: FileSystemClient) -> None:
        self._root = project_root.resolve()
        self._fs = fs
        self._specs_dir = self._root / "specs"
        self._features_dir = self._specs_dir / "features"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_features(self, prd_content: str) -> list[FeatureBoundary]:
        """Parse prd_content and return detected feature boundaries.

        Uses heading-based detection first; falls back to AC-grouping when
        fewer than 2 features are found by the heading pass.
        """
        features = self._detect_by_headings(prd_content)
        if len(features) < 2:
            features = self._detect_by_ac_grouping(prd_content)
        return features[:MAX_FEATURES]

    def decompose(
        self,
        dry_run: bool = False,
        force: bool = False,
        target: str | None = None,
    ) -> DecompositionResult:
        """Run full decomposition against specs/prd.md.

        Args:
            dry_run:  If True, return a result without writing any files.
            force:    If True, overwrite existing feature directories.
            target:   Only decompose this feature (slug or heading text).

        Returns:
            DecompositionResult describing what was (or would be) created.
        """
        prd_path = self._specs_dir / "prd.md"
        if not self._fs.file_exists(prd_path):
            return DecompositionResult(dry_run=dry_run)

        prd_content = self._fs.read_file(prd_path)
        features = self.detect_features(prd_content)

        # Filter to target feature if requested
        if target:
            target_slug = self._slugify(target) if not target.replace("-", "").isalpha() else target
            features = [f for f in features if f.slug == target_slug or f.title == target]

        # Enforce max-features cap
        features = features[:MAX_FEATURES]

        # Compute all AC IDs in prd.md
        all_prd_acs = set(_AC_PATTERN.findall(prd_content))
        assigned_acs: set[str] = set()

        skipped: list[dict[str, str]] = []
        files_created: list[str] = []
        processed_features: list[FeatureBoundary] = []

        for boundary in features:
            feature_dir = self._features_dir / boundary.slug
            if self._fs.directory_exists(feature_dir) and not force:
                skipped.append({"slug": boundary.slug, "reason": "already_exists"})
                continue

            processed_features.append(boundary)
            assigned_acs.update(boundary.acs)

            if not dry_run:
                self._fs.ensure_directory(feature_dir)
                prd_file = self._write_feature_prd(boundary)
                arch_file = self._write_feature_arch_stub(boundary)
                tasks_file = self._write_feature_tasks_stub(boundary)
                files_created.extend(
                    [
                        str(prd_file.relative_to(self._root)),
                        str(arch_file.relative_to(self._root)),
                        str(tasks_file.relative_to(self._root)),
                    ]
                )

        if not dry_run and processed_features:
            self._patch_root_prd(processed_features)

        unassigned = sorted(all_prd_acs - assigned_acs)
        coverage = len(assigned_acs) / len(all_prd_acs) * 100 if all_prd_acs else 0.0

        return DecompositionResult(
            features=processed_features,
            skipped=skipped,
            unassigned_acs=unassigned,
            coverage_pct=round(coverage, 1),
            files_created=files_created,
            dry_run=dry_run,
        )

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _detect_by_headings(self, content: str) -> list[FeatureBoundary]:
        """Pass 1: find features via H2/H3 headings that look like feature sections."""
        lines = content.splitlines()
        headings: list[tuple[int, int, str]] = []  # (line_idx, level, title)
        for i, line in enumerate(lines):
            m = re.match(r"^(#{2,3}) (.+)", line)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
                headings.append((i, level, title))

        features: list[FeatureBoundary] = []
        for idx, (line_start, level, title) in enumerate(headings):
            # Only consider headings that look like feature/section markers
            if not _FEATURE_KEYWORD_RE.search(title):
                continue

            # Find the line where this section ends (next same-level heading)
            line_end = len(lines)
            for future_line, future_level, _ in headings[idx + 1 :]:
                if future_level <= level:
                    line_end = future_line
                    break

            section_lines = lines[line_start:line_end]
            section_text = "\n".join(section_lines)

            acs = _AC_PATTERN.findall(section_text)
            has_user_story = bool(_USER_STORY_RE.search(section_text))

            if not acs and not has_user_story:
                continue

            slug = self._slugify(title)
            if not slug:
                continue

            # Deduplicate slugs
            if any(f.slug == slug for f in features):
                slug = f"{slug}-{len(features)}"

            features.append(
                FeatureBoundary(
                    slug=slug,
                    title=title,
                    acs=list(dict.fromkeys(acs)),
                    content_blocks=section_lines,
                    source_line_start=line_start,
                    source_line_end=line_end - 1,
                )
            )

        return features

    def _detect_by_ac_grouping(self, content: str) -> list[FeatureBoundary]:
        """Pass 2 (fallback): group AC-XX entries by surrounding H3 heading."""
        lines = content.splitlines()
        features: list[FeatureBoundary] = []
        current_h3: str | None = None
        current_h3_line: int = 0
        current_acs: list[str] = []
        current_lines: list[str] = []

        def _flush(end_line: int) -> None:
            nonlocal current_h3, current_acs, current_lines
            if current_h3 and len(current_acs) >= 2:
                slug = self._slugify(current_h3)
                if slug:
                    features.append(
                        FeatureBoundary(
                            slug=slug,
                            title=current_h3,
                            acs=list(dict.fromkeys(current_acs)),
                            content_blocks=list(current_lines),
                            source_line_start=current_h3_line,
                            source_line_end=end_line,
                        )
                    )
            current_h3 = None
            current_acs = []
            current_lines = []

        for i, line in enumerate(lines):
            h3_m = re.match(r"^### (.+)", line)
            if h3_m:
                _flush(i - 1)
                current_h3 = h3_m.group(1).strip()
                current_h3_line = i
                current_lines = [line]
                continue

            if current_h3:
                current_lines.append(line)
                found = _AC_PATTERN.findall(line)
                current_acs.extend(found)

        _flush(len(lines) - 1)
        return features

    # ------------------------------------------------------------------
    # Slug generation
    # ------------------------------------------------------------------

    def _slugify(self, heading: str) -> str:
        """Convert a heading to a kebab-case slug, stripping feature prefixes."""
        # 1. Strip leading numbered prefix: "2.1 " or "3. "
        heading = re.sub(r"^[\d]+\.[\d]*\s+", "", heading, flags=re.IGNORECASE)
        # 2. Strip "Feature A:" / "Feature 1:" style prefix
        heading = re.sub(r"^feature\s+\w+[:.]?\s*", "", heading, flags=re.IGNORECASE)
        # 3. Strip "Section 1:" style prefix
        heading = re.sub(r"^section\s+\w+[:.]?\s*", "", heading, flags=re.IGNORECASE)
        heading = heading.lower()
        heading = re.sub(r"[^a-z0-9]+", "-", heading)
        return heading.strip("-")

    # ------------------------------------------------------------------
    # File writers
    # ------------------------------------------------------------------

    def _write_feature_prd(self, boundary: FeatureBoundary) -> Path:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        content_text = "\n".join(boundary.content_blocks)
        content = f"""\
# Feature: {boundary.title}

**Version:** 1.0
**Date:** {date}
**Status:** 🔵 Decomposed from root PRD
**Parent PRD:** [specs/prd.md](../../prd.md)

> Decomposed by `sdd_decompose_specs` on {date}.
> Original section: "{boundary.title}" (lines {boundary.source_line_start}-{boundary.source_line_end})

---

{content_text}
"""
        path = self._features_dir / boundary.slug / "prd.md"
        self._fs.write_file(path, content)
        return path

    def _write_feature_arch_stub(self, boundary: FeatureBoundary) -> Path:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        content = f"""\
# Architecture: {boundary.title}

**Version:** 1.0
**Date:** {date}
**Status:** 🔵 Stub — Pending Architect Review
**Parent Architecture:** [specs/arch.md](../../arch.md)

> This stub was generated by `sdd_decompose_specs`.
> The Architect role will populate this file during the review cycle.

---

## Architecture

<!-- To be populated by the Architect role -->
<!-- Run: goose run --recipe specs/recipes/architect.yaml -->
"""
        path = self._features_dir / boundary.slug / "arch.md"
        self._fs.write_file(path, content)
        return path

    def _write_feature_tasks_stub(self, boundary: FeatureBoundary) -> Path:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        content = f"""\
# Tasks: {boundary.title}

**Feature:** {boundary.slug}
**Date:** {date}
**Based on:** [prd.md](./prd.md) v1.0
**Parent Tasks:** [specs/tasks.md](../../tasks.md)

> This stub was generated by `sdd_decompose_specs`.

---

## Role Review Checklist

{_ROLE_CHECKLIST}

---

## Completed

| ID | Title | Role | Completed |
|----|-------|------|-----------|

---

## In Progress

| ID | Title | Role | Started |
|----|-------|------|---------|

---

## Pending

| ID | Title | Role | Priority |
|----|-------|------|----------|
"""
        path = self._features_dir / boundary.slug / "tasks.md"
        self._fs.write_file(path, content)
        return path

    def _patch_root_prd(self, features: list[FeatureBoundary]) -> None:
        """Add or update a ## Feature Index section in specs/prd.md."""
        prd_path = self._specs_dir / "prd.md"
        if not self._fs.file_exists(prd_path):
            return

        existing = self._fs.read_file(prd_path)
        index_heading = "## Feature Index"

        # Build the new index block
        rows = "\n".join(f"- [{f.title}](features/{f.slug}/prd.md)" for f in features)
        new_section = f"{index_heading}\n\n{rows}\n"

        if index_heading in existing:
            # Replace everything from the heading to the next H2 (or EOF)
            updated = re.sub(
                r"## Feature Index.*?(?=\n## |\Z)",
                new_section,
                existing,
                flags=re.DOTALL,
            )
        else:
            updated = existing.rstrip("\n") + f"\n\n---\n\n{new_section}"

        self._fs.write_file(prd_path, updated)
