from pathlib import Path

RELEASE_WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "release.yml"


def test_live_probe_runs_only_for_tags_and_manual_dispatch() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    job = workflow.split("  hermes-compatibility:\n", 1)[1]

    assert "if: github.event_name == 'workflow_dispatch' || startsWith(" in job
    assert "github.ref, 'refs/tags/v'" in job
    assert "needs: [test, package]" in job
    assert 'node-version: "22"' in job
    assert "git -C /tmp/hermes-agent checkout 4281151ae859241351ba14d8c7682dc67ff4c126" in job
    assert (
        "git -C /tmp/hermes-agent update-ref refs/remotes/origin/main "
        "4281151ae859241351ba14d8c7682dc67ff4c126"
    ) in job
    assert (
        "git -C /tmp/hermes-agent remote set-url origin "
        "file:///tmp/hermes-agent-pinned-origin"
    ) in job
    assert "npm ci --workspace web && npm run build -w web" in job
    assert "python scripts/probe_hermes_compatibility.py" in job
    assert "python scripts/probe_hermes_dashboard_compatibility.py" in job
    assert "github.event_name == 'push'" not in job
    assert "github.event_name == 'pull_request'" not in job
