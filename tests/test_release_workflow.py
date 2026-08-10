from pathlib import Path

RELEASE_WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "release.yml"


def test_live_probe_runs_only_for_tags_and_manual_dispatch() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    job = workflow.split("  hermes-compatibility:\n", 1)[1]

    assert "if: github.event_name == 'workflow_dispatch' || startsWith(" in job
    assert "github.ref, 'refs/tags/v'" in job
    assert "needs: [test, package]" in job
    assert 'node-version: "26"' in job
    assert (
        "git -C /tmp/hermes-v0182-source checkout "
        "4281151ae859241351ba14d8c7682dc67ff4c126"
    ) in job
    assert (
        "git -C /tmp/hermes-v0182-source update-ref refs/remotes/origin/main "
        "4281151ae859241351ba14d8c7682dc67ff4c126"
    ) in job
    assert (
        "git -C /tmp/hermes-v0182-source remote set-url origin "
        "file:///tmp/hermes-v0182-pinned-origin"
    ) in job
    assert (
        "git -C /tmp/hermes-v0190-source checkout "
        "3ef6bbd201263d354fd83ec55b3c306ded2eb72a"
    ) in job
    assert (
        "git -C /tmp/hermes-v0190-source update-ref refs/remotes/origin/main "
        "3ef6bbd201263d354fd83ec55b3c306ded2eb72a"
    ) in job
    assert (
        "git -C /tmp/hermes-v0190-source remote set-url origin "
        "file:///tmp/hermes-v0190-pinned-origin"
    ) in job
    assert (
        "git -C /tmp/hermes-v0200-source checkout "
        "3c27eb6234bf91b8ceee9e9071591b31e9b148cb"
    ) in job
    assert (
        "git -C /tmp/hermes-v0200-source update-ref refs/remotes/origin/main "
        "3c27eb6234bf91b8ceee9e9071591b31e9b148cb"
    ) in job
    assert (
        "git -C /tmp/hermes-v0200-source remote set-url origin "
        "file:///tmp/hermes-v0200-pinned-origin"
    ) in job
    assert job.count("npm ci --workspace web && npm run build -w web") == 3
    assert "python scripts/run_hermes_support_matrix.py" in job
    assert (
        "--host supported-v0182 0.18.2 2026.7.7.2 "
        "4281151ae859241351ba14d8c7682dc67ff4c126"
    ) in job
    assert (
        "--host supported-v0190 0.19.0 2026.7.20 "
        "3ef6bbd201263d354fd83ec55b3c306ded2eb72a"
    ) in job
    assert (
        "--host supported-v0200 0.20.0 2026.8.3 "
        "3c27eb6234bf91b8ceee9e9071591b31e9b148cb"
    ) in job
    assert "/tmp/hermes-v0182/bin/pip install /tmp/hermes-v0182-source" in job
    assert "/tmp/hermes-v0190/bin/pip install /tmp/hermes-v0190-source" in job
    assert "/tmp/hermes-v0200/bin/pip install -e /tmp/hermes-v0200-source" in job
    assert 'v0182_purelib="$(/tmp/hermes-v0182/bin/python -c' in job
    assert (
        "4281151ae859241351ba14d8c7682dc67ff4c126 > "
        '"$v0182_purelib/.hermes_build_sha"'
    ) in job
    assert 'v0190_purelib="$(/tmp/hermes-v0190/bin/python -c' in job
    assert (
        "3ef6bbd201263d354fd83ec55b3c306ded2eb72a > "
        '"$v0190_purelib/.hermes_build_sha"'
    ) in job
    assert 'v0200_purelib="$(/tmp/hermes-v0200/bin/python -c' in job
    assert (
        "3c27eb6234bf91b8ceee9e9071591b31e9b148cb > "
        '"$v0200_purelib/.hermes_build_sha"'
    ) in job
    assert "python -m pip install -e ." not in job
    assert "github.event_name == 'push'" not in job
    assert "github.event_name == 'pull_request'" not in job


def test_release_workflow_checks_and_hashes_one_exact_wheel_before_matrix() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    package = workflow.split("  package:\n", 1)[1].split(
        "  hermes-compatibility:\n", 1
    )[0]
    compatibility = workflow.split("  hermes-compatibility:\n", 1)[1]

    assert "actions/upload-artifact@v6" in package
    assert "name: daidala-dist" in package
    assert "actions/download-artifact@v6" in compatibility
    assert "cache: npm" not in compatibility
    assert 'test "${#wheels[@]}" -eq 1' in compatibility
    hash_index = compatibility.index('wheel_sha256="$(sha256sum')
    orchestrator_install_index = compatibility.index('python -m pip install "$wheel"')
    matrix_index = compatibility.index("python scripts/run_hermes_support_matrix.py")
    assert hash_index < orchestrator_install_index < matrix_index
    assert '--expected-wheel-sha256 "$wheel_sha256"' in compatibility
