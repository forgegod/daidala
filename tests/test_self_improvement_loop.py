from __future__ import annotations

import re
from pathlib import Path

import yaml

from daidala.constraints import parse_workflow_constraints
from daidala.projects import parse_project_manifest

ROOT = Path(__file__).parents[1]


def test_self_improvement_repository_fixtures_are_consistent() -> None:
    manifest = parse_project_manifest((ROOT / ".daidala/project.yaml").read_text())
    constraints = parse_workflow_constraints(
        (ROOT / manifest.default_constraints_source).read_text(encoding="utf-8")
    )
    limits = yaml.safe_load(
        (ROOT / "docs/evaluation-results/v1/experiment-limits.yaml").read_text()
    )

    assert limits["project_id"] == manifest.project_id
    assert limits["active_cycles"] == 1
    assert limits["system_boundaries"]["evaluator_backend"] == "restricted-container"
    assert constraints.global_constraints


def test_issue_template_requires_structured_phase_one_fields_without_readiness() -> None:
    template = yaml.safe_load(
        (ROOT / ".github/ISSUE_TEMPLATE/daidala-self-improvement.yml").read_text()
    )
    ids = {row["id"] for row in template["body"]}

    assert ids == {
        "category",
        "source_identity",
        "expected",
        "observed",
        "evidence",
        "acceptance",
        "dependencies",
        "priority",
        "publication",
    }
    assert template["labels"] == ["daidala-si"]
    assert "daidala-si:ready" not in template["labels"]


def test_stable_case_matrix_materializes_every_f01_through_f18_area() -> None:
    result = (ROOT / "docs/evaluation-results/v1/daidala-self-improvement.md").read_text()
    areas = {
        int(match)
        for match in re.findall(r"TC-F(\d{2})-\d{2}", result)
    }

    assert areas == set(range(1, 19))
    assert "No setup mutation" in result
    assert "Status: `not-run`" in result


def test_result_record_reconciles_completed_uc01_pack_runs() -> None:
    result = (ROOT / "docs/evaluation-results/v1/daidala-self-improvement.md").read_text()

    assert "cycle-21158b4320bf09968915110abdfeb32ac2a0c833acfe90a99bf340936c148f55" in result
    assert "cycle-98afe833a63afdbfce7a16bcd9741d4475e46cfb47013c2982cbe3ad04653c26" in result
    assert "Pack comparison: `incomparable`" in result
    assert "No preferred pack is selected" in result
    assert "UC-01 remains blocked before mutation" not in result
