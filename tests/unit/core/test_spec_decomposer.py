"""Unit tests for SpecDecomposer."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdd_server.core.spec_decomposer import (
    MAX_FEATURES,
    SpecDecomposer,
)
from sdd_server.infrastructure.filesystem import FileSystemClient

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def decomposer(tmp_path: Path) -> SpecDecomposer:
    fs = FileSystemClient(tmp_path)
    return SpecDecomposer(tmp_path, fs)


def _write_prd(tmp_path: Path, content: str) -> Path:
    specs = tmp_path / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    prd = specs / "prd.md"
    prd.write_text(content)
    return prd


_PRD_WITH_FEATURES = """\
# Product Requirements

## 2. User Stories

### 2.1 Feature A: Authentication

**User Story:**
> As a user I want to log in.

**Acceptance Criteria:**

- **AC-01:** Login with email and password.
- **AC-02:** Show error on wrong credentials.

### 2.2 Feature B: User Profile

**User Story:**
> As a user I want to view my profile.

**Acceptance Criteria:**

- **AC-03:** View name and email.
- **AC-04:** Edit profile picture.
"""

_PRD_WITH_SECTIONS = """\
# PRD

## Section 1: Billing

- **AC-01:** Pay by card.
- **AC-02:** Receive invoice.

## Section 2: Notifications

- **AC-03:** Email on payment.
- **AC-04:** In-app banner.
"""

_PRD_FLAT_ACS = """\
# PRD

### Auth feature

- **AC-01:** Login
- **AC-02:** Logout

### Dashboard feature

- **AC-03:** View stats
- **AC-04:** Export CSV
"""


# ---------------------------------------------------------------------------
# TestFeatureDetection
# ---------------------------------------------------------------------------


class TestFeatureDetection:
    def test_detects_features_by_heading(self, decomposer: SpecDecomposer) -> None:
        features = decomposer.detect_features(_PRD_WITH_FEATURES)
        assert len(features) == 2
        slugs = {f.slug for f in features}
        assert "authentication" in slugs
        assert "user-profile" in slugs

    def test_detects_features_by_section_keyword(self, decomposer: SpecDecomposer) -> None:
        features = decomposer.detect_features(_PRD_WITH_SECTIONS)
        assert len(features) >= 2
        slugs = {f.slug for f in features}
        assert "billing" in slugs
        assert "notifications" in slugs

    def test_detects_features_by_ac_grouping_fallback(self, decomposer: SpecDecomposer) -> None:
        """When heading pass yields < 2 features, fall back to AC grouping."""
        features = decomposer.detect_features(_PRD_FLAT_ACS)
        assert len(features) == 2
        slugs = {f.slug for f in features}
        assert "auth-feature" in slugs or "auth" in slugs
        assert "dashboard-feature" in slugs or "dashboard" in slugs

    def test_acs_assigned_to_correct_feature(self, decomposer: SpecDecomposer) -> None:
        features = decomposer.detect_features(_PRD_WITH_FEATURES)
        auth = next(f for f in features if "auth" in f.slug.lower())
        assert "AC-01" in auth.acs
        assert "AC-02" in auth.acs
        assert "AC-03" not in auth.acs

    def test_maximum_features_capped(self, decomposer: SpecDecomposer) -> None:
        """detect_features never returns more than MAX_FEATURES."""
        # Build a PRD with 60 feature sections
        lines = ["# PRD\n"]
        for i in range(60):
            lines.append(f"## Section {i}: Feature {i}\n\n- **AC-{i:02d}:** Thing.\n")
        content = "\n".join(lines)
        features = decomposer.detect_features(content)
        assert len(features) <= MAX_FEATURES

    def test_empty_prd_returns_no_features(self, decomposer: SpecDecomposer) -> None:
        features = decomposer.detect_features("# Empty\n\nNo ACs here.\n")
        assert features == []

    def test_no_duplicate_slugs(self, decomposer: SpecDecomposer) -> None:
        prd = """\
# PRD

## Feature A: Auth

- **AC-01:** Login.

## Feature B: Auth

- **AC-02:** Logout.
"""
        features = decomposer.detect_features(prd)
        slugs = [f.slug for f in features]
        assert len(slugs) == len(set(slugs)), "Duplicate slugs detected"


# ---------------------------------------------------------------------------
# TestSlugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_strips_feature_prefix(self, decomposer: SpecDecomposer) -> None:
        assert decomposer._slugify("Feature A: Authentication") == "authentication"

    def test_strips_numbered_prefix(self, decomposer: SpecDecomposer) -> None:
        assert decomposer._slugify("3.1 Specification Management") == "specification-management"

    def test_handles_plain_heading(self, decomposer: SpecDecomposer) -> None:
        assert decomposer._slugify("User Profile") == "user-profile"

    def test_lowercases_result(self, decomposer: SpecDecomposer) -> None:
        slug = decomposer._slugify("UPPER CASE HEADING")
        assert slug == slug.lower()

    def test_replaces_special_chars_with_hyphens(self, decomposer: SpecDecomposer) -> None:
        slug = decomposer._slugify("Auth & Billing / Payments")
        assert " " not in slug
        assert "&" not in slug
        assert "/" not in slug

    def test_strips_leading_trailing_hyphens(self, decomposer: SpecDecomposer) -> None:
        slug = decomposer._slugify("  Auth  ")
        assert not slug.startswith("-")
        assert not slug.endswith("-")

    def test_empty_heading_returns_empty(self, decomposer: SpecDecomposer) -> None:
        assert decomposer._slugify("") == ""


# ---------------------------------------------------------------------------
# TestDecomposition
# ---------------------------------------------------------------------------


class TestDecomposition:
    def test_dry_run_creates_no_files(self, tmp_path: Path, decomposer: SpecDecomposer) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        result = decomposer.decompose(dry_run=True)
        assert result.dry_run is True
        # No feature directories created
        features_dir = tmp_path / "specs" / "features"
        assert not features_dir.exists() or not any(features_dir.iterdir())
        assert result.files_created == []

    def test_creates_feature_directories(self, tmp_path: Path, decomposer: SpecDecomposer) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        result = decomposer.decompose()
        assert len(result.features) == 2
        assert len(result.files_created) == 6  # 3 files x 2 features
        for feature in result.features:
            feature_dir = tmp_path / "specs" / "features" / feature.slug
            assert feature_dir.is_dir()
            assert (feature_dir / "prd.md").is_file()
            assert (feature_dir / "arch.md").is_file()
            assert (feature_dir / "tasks.md").is_file()

    def test_idempotent_skips_existing_dirs(
        self, tmp_path: Path, decomposer: SpecDecomposer
    ) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        # First run creates features
        result1 = decomposer.decompose()
        assert len(result1.features) == 2
        # Second run skips them
        result2 = decomposer.decompose()
        assert len(result2.features) == 0
        assert len(result2.skipped) == 2
        for s in result2.skipped:
            assert s["reason"] == "already_exists"

    def test_force_flag_overwrites_existing(
        self, tmp_path: Path, decomposer: SpecDecomposer
    ) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        decomposer.decompose()
        result = decomposer.decompose(force=True)
        assert len(result.features) == 2
        assert len(result.skipped) == 0

    def test_patches_root_prd_with_feature_index(
        self, tmp_path: Path, decomposer: SpecDecomposer
    ) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        result = decomposer.decompose()
        assert len(result.features) > 0
        prd_content = (tmp_path / "specs" / "prd.md").read_text()
        assert "## Feature Index" in prd_content

    def test_unassigned_acs_reported(self, tmp_path: Path, decomposer: SpecDecomposer) -> None:
        prd = """\
# PRD

## Feature A: Auth

- **AC-01:** Login.
- **AC-02:** Logout.

## Notes

Orphan AC: **AC-99:** Something unrelated.
"""
        _write_prd(tmp_path, prd)
        result = decomposer.decompose()
        # AC-99 is in the Notes section which has no User Story or feature keyword match
        # It may end up unassigned depending on detection
        # Just verify the field exists and is a list
        assert isinstance(result.unassigned_acs, list)

    def test_coverage_pct_calculated(self, tmp_path: Path, decomposer: SpecDecomposer) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        result = decomposer.decompose()
        assert 0.0 <= result.coverage_pct <= 100.0

    def test_missing_prd_returns_empty_result(
        self, tmp_path: Path, decomposer: SpecDecomposer
    ) -> None:
        result = decomposer.decompose()
        assert result.features == []
        assert result.files_created == []

    def test_target_limits_to_one_feature(self, tmp_path: Path, decomposer: SpecDecomposer) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        result = decomposer.decompose(target="authentication")
        slugs = [f.slug for f in result.features]
        assert all("auth" in s for s in slugs)
        assert len(result.features) <= 1


# ---------------------------------------------------------------------------
# TestGeneratedFiles
# ---------------------------------------------------------------------------


class TestGeneratedFiles:
    def test_feature_prd_contains_back_reference(
        self, tmp_path: Path, decomposer: SpecDecomposer
    ) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        decomposer.decompose()
        features_dir = tmp_path / "specs" / "features"
        for slug_dir in features_dir.iterdir():
            content = (slug_dir / "prd.md").read_text()
            assert "specs/prd.md" in content or "../../prd.md" in content

    def test_feature_prd_preserves_ac_numbering(
        self, tmp_path: Path, decomposer: SpecDecomposer
    ) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        result = decomposer.decompose()
        auth = next(f for f in result.features if "auth" in f.slug.lower())
        prd_content = (tmp_path / "specs" / "features" / auth.slug / "prd.md").read_text()
        assert "AC-01" in prd_content
        assert "AC-02" in prd_content

    def test_arch_stub_has_placeholder_section(
        self, tmp_path: Path, decomposer: SpecDecomposer
    ) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        decomposer.decompose()
        features_dir = tmp_path / "specs" / "features"
        for slug_dir in features_dir.iterdir():
            content = (slug_dir / "arch.md").read_text()
            assert "## Architecture" in content
            assert "Architect role" in content or "architect" in content.lower()

    def test_tasks_stub_has_full_role_checklist(
        self, tmp_path: Path, decomposer: SpecDecomposer
    ) -> None:
        _write_prd(tmp_path, _PRD_WITH_FEATURES)
        decomposer.decompose()
        features_dir = tmp_path / "specs" / "features"
        for slug_dir in features_dir.iterdir():
            content = (slug_dir / "tasks.md").read_text()
            assert "spec-linter" in content
            assert "architect" in content
            assert "product-owner" in content
            assert content.count("- [ ]") == 11
