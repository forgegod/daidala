#!/usr/bin/env python3
"""Probe packaged Daidala plugin loading through public Hermes CLI surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from probe_hermes_compatibility import (
    SUPPORTED_HOST,
    HostIdentity,
    ProbeError,
    add_expected_host_arguments,
    expected_host_from_args,
    parse_json,
    require_isolated_root,
    require_version,
    run,
)

from daidala.constraints import parse_workflow_constraints
from daidala.packs import load_pack, pack_content_digest
from daidala.projects import parse_project_manifest
from daidala.registrations import parse_controller_registration
from daidala.state import WorkflowStage

PACKS = ("addyosmani", "aidlc")
PLUGIN_NAME = "daidala"
PLUGIN_VERSION = "0.2.0"


def _prepare_home(home: Path, plugin_directory: Path | None) -> None:
    home.mkdir(parents=True)
    (home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - daidala\n",
        encoding="utf-8",
    )
    if plugin_directory is None:
        return
    source = plugin_directory.expanduser().resolve()
    if not (source / "plugin.yaml").is_file() or not (source / "__init__.py").is_file():
        raise ProbeError("plugin directory must contain plugin.yaml and __init__.py")
    destination = home / "plugins" / PLUGIN_NAME
    destination.parent.mkdir(parents=True)
    destination.symlink_to(source, target_is_directory=True)


def _plugin_inventory(hermes: str, env: dict[str, str]) -> dict[str, Any] | None:
    payload = parse_json(
        run([hermes, "plugins", "list", "--enabled", "--json"], env=env),
        "enabled plugin inventory",
    )
    if not isinstance(payload, list):
        raise ProbeError("enabled plugin inventory is not a JSON list")
    plugin = next(
        (item for item in payload if isinstance(item, dict) and item.get("name") == PLUGIN_NAME),
        None,
    )
    if plugin is None:
        return None
    if plugin.get("status") != "enabled":
        raise ProbeError(f"Daidala plugin is not enabled: {plugin.get('status')!r}")
    if plugin.get("version") != PLUGIN_VERSION:
        raise ProbeError(
            f"Daidala plugin version drifted: expected {PLUGIN_VERSION}, "
            f"observed {plugin.get('version')!r}"
        )
    return plugin


def _validate_pack(command: list[str], env: dict[str, str], label: str) -> dict[str, Any]:
    payload = parse_json(run(command, env=env), label)
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ProbeError(f"{label} did not return a successful pack result")
    return payload


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _git(command: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise ProbeError(result.stderr.strip() or f"command failed: {' '.join(command)}")
    return result.stdout.strip()


def _issue_body() -> str:
    return (
        "### Category\n\nregression\n\n"
        "### Originating experiment, test case, or source identity\n\nUC-01 / TC-F04-01\n\n"
        "### Expected behavior\n\nThe temporary calculator returns 2.\n\n"
        "### Observed behavior\n\nThe temporary calculator returns 1.\n\n"
        "### Redacted evidence reference and SHA-256 digest\n\n"
        f"uc-01 sha256:{'a' * 64}\n\n"
        "### Acceptance criteria\n\n- The failing test passes.\n\n"
        "### Dependencies and risk\n\nTemporary fixture only.\n\n"
        "### Priority\n\n1\n\n### Publication state\n\nlocal\n"
    )


def _snapshot(paths: list[Path]) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for path in paths:
        if not path.exists():
            snapshot[str(path)] = None
        elif path.is_file():
            snapshot[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            snapshot[str(path)] = [
                (str(item.relative_to(path)), hashlib.sha256(item.read_bytes()).hexdigest())
                for item in sorted(path.rglob("*"))
                if item.is_file()
            ]
    return snapshot


def _prepare_git_repository(path: Path, remote: str, env: dict[str, str]) -> str:
    path.mkdir(parents=True)
    _git(["git", "init", "-q", str(path)], env)
    _git(["git", "-C", str(path), "config", "user.name", "Daidala Probe"], env)
    _git(["git", "-C", str(path), "config", "user.email", "probe@example.invalid"], env)
    _git(["git", "-C", str(path), "remote", "add", "origin", remote], env)
    return ""


def _write_fake_boundaries(
    bin_dir: Path,
    *,
    home: Path,
    checkout: Path,
    issue_file: Path,
    command_log: Path,
) -> None:
    bin_dir.mkdir(parents=True)
    project = {"id": "PVT_kwDOExample", "url": "https://github.com/users/forgegod/projects/1"}
    _write_executable(
        bin_dir / "gh",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            with Path({str(command_log)!r}).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(["gh", *args]) + "\\n")
            issue = json.loads(Path({str(issue_file)!r}).read_text(encoding="utf-8"))
            if args[:2] == ["issue", "view"]:
                print(json.dumps(issue, sort_keys=True))
            elif args[:2] == ["issue", "list"]:
                print('[{{"number":42}}]')
            elif args[:2] == ["project", "list"]:
                print(json.dumps({{"projects": [{project!r}], "totalCount": 1}}, sort_keys=True))
            elif args[:2] == ["api", "--paginate"] and "/events?" in args[2]:
                event = {{
                    "event": "labeled",
                    "label": {{"name": "daidala-si:ready"}},
                    "actor": {{"login": "forgegod"}},
                }}
                print(json.dumps(event, sort_keys=True))
            elif args[:2] == ["api", "--paginate"] and "/comments?" in args[2]:
                pass
            else:
                print("unexpected gh mutation boundary", file=sys.stderr)
                raise SystemExit(97)
            """
        ),
    )
    _write_executable(
        bin_dir / "hermes",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            with Path({str(command_log)!r}).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(["hermes", *args]) + "\\n")
            if args == ["profile", "list"]:
                print(" ◆daidala-self-improvement\\n  hermes-vc")
            elif args == ["profile", "show", "daidala-self-improvement"]:
                print("Profile: daidala-self-improvement\\nPath:    {home}")
            elif args[-4:] == ["plugins", "list", "--no-bundled", "--json"]:
                print('[{{"name":"daidala","status":"enabled"}}]')
            elif args == ["kanban", "boards", "list", "--json"]:
                board = {{
                    "slug": "daidala-forgegod-daidala",
                    "archived": False,
                    "default_workdir": {str(checkout)!r},
                }}
                print(json.dumps([board], sort_keys=True))
            elif args[-2:] == ["stats", "--json"]:
                print('{{"counts":{{}},"total":0}}')
            elif "packs" in args and "validate" in args:
                print('{{}}')
            elif args[-2:] == ["gateway", "status"]:
                print("Gateway running")
            else:
                print("unexpected Hermes mutation boundary", file=sys.stderr)
                raise SystemExit(97)
            """
        ),
    )
    _write_executable(
        bin_dir / "docker",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            with Path({str(command_log)!r}).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(["docker", *args]) + "\\n")
            if args[:1] == ["version"]:
                print("27.0|27.0")
            elif args[:2] == ["network", "inspect"]:
                print("none|null")
            elif args[:2] == ["image", "inspect"]:
                print("sha256:" + "b" * 64)
            else:
                raise SystemExit(97)
            """
        ),
    )


def _prepare_admission_fixture(root: Path, home: Path, env: dict[str, str]) -> dict[str, Any]:
    source_root = Path(__file__).resolve().parents[1]
    checkout = root / "checkout"
    remote = "git@github.com:forgegod/daidala.git"
    _prepare_git_repository(checkout, remote, env)
    policy = checkout / ".daidala"
    policy.mkdir()
    for name in ("project.yaml", "constraints.yaml"):
        shutil.copy2(source_root / ".daidala" / name, policy / name)
    (checkout / "README.md").write_text("Daidala compatibility fixture.\n", encoding="utf-8")
    _git(["git", "-C", str(checkout), "add", "."], env)
    _git(["git", "-C", str(checkout), "commit", "-q", "-m", "fixture"], env)
    baseline = _git(["git", "-C", str(checkout), "rev-parse", "HEAD"], env)

    plugin_checkout = home / "plugins" / PLUGIN_NAME
    _prepare_git_repository(plugin_checkout, remote, env)
    (plugin_checkout / "README.md").write_text("Controller revision fixture.\n", encoding="utf-8")
    _git(["git", "-C", str(plugin_checkout), "add", "."], env)
    _git(["git", "-C", str(plugin_checkout), "commit", "-q", "-m", "fixture"], env)
    controller_revision = _git(
        ["git", "-C", str(plugin_checkout), "rev-parse", "HEAD"], env
    )

    project_root = home / "projects" / "forgegod-daidala"
    project_root.mkdir(parents=True)
    registration = project_root / "registration.yaml"
    registration.write_text(
        textwrap.dedent(
            f"""\
            schema: daidala.controller-registration/v2
            project_id: forgegod-daidala
            checkout: {checkout}
            controller_profile: daidala-self-improvement
            board: daidala-forgegod-daidala
            repository_identity:
              canonical: forgegod/daidala
              verified_remote: {remote}
            credentials:
              intake: github-read
              findings: github-write
            approval:
              maintainers: [forgegod]
            notifications:
              adapter: hermes-gateway
              target: attended-daidala
              destination: telegram:-1001234567890:17585
            evaluator:
              backend: restricted-container
              network: denied-by-default
            limits:
              active_cycles: 1
              goal_turns: 12
              delegated_workers: 3
              research_query_batches: 3
              extracted_sources: 3
              wall_clock_seconds: 3600
            """
        ),
        encoding="utf-8",
    )
    bindings = project_root / "credential-bindings.yaml"
    bindings.write_text(
        """schema: daidala.credential-bindings/v1
project_id: forgegod-daidala
bindings:
  - alias: github-read
    resolver: environment
    environment_variable: DAIDALA_PROBE_GITHUB_READ
  - alias: github-write
    resolver: environment
    environment_variable: DAIDALA_PROBE_GITHUB_WRITE
""",
        encoding="utf-8",
    )
    denied = ["contents-write", "administration", "merge", "release", "deployment"]
    evidence = project_root / "prerequisite-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema": "daidala.prerequisite-evidence/v1",
                "project_id": "forgegod-daidala",
                "approved_controller_revision": controller_revision,
                "sticky_profile": "hermes-vc",
                "credential_capabilities": [
                    {
                        "alias": "github-read",
                        "capability": "github-intake",
                        "allowed": [
                            "read-organization",
                            "read-project",
                            "read-public-repository",
                        ],
                        "denied": denied,
                        "expires_on": "2099-12-31",
                        "read_probe_receipt": "probe-read",
                        "write_probe_identity": None,
                    },
                    {
                        "alias": "github-write",
                        "capability": "github-findings",
                        "allowed": ["metadata-read", "issues-read-write"],
                        "denied": denied,
                        "expires_on": "2099-12-31",
                        "read_probe_receipt": "probe-findings",
                        "write_probe_identity": "probe-controlled-write",
                    },
                ],
                "github_project": {
                    "owner": "forgegod",
                    "project_id": "PVT_kwDOExample",
                    "url": "https://github.com/users/forgegod/projects/1",
                    "fields": [
                        "category",
                        "priority",
                        "readiness",
                        "claim-owner",
                        "claim-lease-expiry",
                        "cycle-id",
                        "workflow-id",
                        "terminal-comparison-outcome",
                    ],
                    "read_probe_receipt": "probe-project",
                },
                "notification": {
                    "adapter": "hermes-gateway",
                    "target_alias": "attended-daidala",
                    "authorized_maintainer": "forgegod",
                    "receipt_id": "probe-notification",
                },
                "evaluator": {
                    "backend": "restricted-container",
                    "network": "denied-by-default",
                    "image_identity": "example/evaluator@sha256:" + "b" * 64,
                    "fresh_home": True,
                    "network_denied": True,
                    "controller_credentials_absent": True,
                    "bounded_mounts": True,
                    "receipt_id": "probe-evaluator",
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    issue_file = root / "issue.json"
    issue_file.write_text(
        json.dumps(
            {
                "number": 42,
                "url": "https://github.com/forgegod/daidala/issues/42",
                "title": "[Daidala SI] Fix temporary calculator",
                "body": _issue_body(),
                "state": "OPEN",
                "labels": [
                    {"name": "daidala-si"},
                    {"name": "daidala-si:ready"},
                    {"name": "daidala-si:regression"},
                    {"name": "daidala-si:priority-1"},
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    command_log = root / "boundary-commands.jsonl"
    command_log.touch()
    _write_fake_boundaries(
        root / "bin",
        home=home,
        checkout=checkout,
        issue_file=issue_file,
        command_log=command_log,
    )
    return {
        "baseline": baseline,
        "checkout": checkout,
        "command_log": command_log,
        "constraints": policy / "constraints.yaml",
        "issue": issue_file,
        "manifest": policy / "project.yaml",
        "project_root": project_root,
        "registration": registration,
        "state_paths": [
            registration,
            bindings,
            evidence,
            issue_file,
            project_root / "cycles",
            home / "daidala",
            home / "kanban.db",
            home / "kanban",
        ],
    }


def _validate_admission(
    native_text: str,
    standalone_text: str,
    fixture: dict[str, Any],
) -> dict[str, Any]:
    if native_text != standalone_text:
        raise ProbeError("native and standalone admission preview JSON differ")
    payload = parse_json(native_text, "project-cycle admission preview")
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ProbeError("project-cycle admission preview was not successful")
    if payload.get("operation") != "project-cycle-admit" or payload.get("dry_run") is not True:
        raise ProbeError("project-cycle admission did not remain a dry run")
    preview = payload.get("preview")
    if not isinstance(preview, dict):
        raise ProbeError("project-cycle admission preview is missing")
    cycle = preview.get("cycle")
    if not isinstance(cycle, dict):
        raise ProbeError("project-cycle admission identity is missing")
    manifest = parse_project_manifest(Path(fixture["manifest"]).read_text(encoding="utf-8"))
    registration = parse_controller_registration(
        Path(fixture["registration"]).read_text(encoding="utf-8")
    )
    constraints = parse_workflow_constraints(
        Path(fixture["constraints"]).read_text(encoding="utf-8")
    )
    pack = load_pack("addyosmani")
    expected_profiles = [
        {"stage": stage.value, "profile": f"probe-{stage.value}"}
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    ]
    exact = {
        "baseline_revision": fixture["baseline"],
        "manifest_digest": manifest.digest,
        "pack_name": "addyosmani",
        "pack_source_revision": pack.source_revision,
        "pack_content_digest": pack_content_digest("addyosmani"),
    }
    if any(cycle.get(key) != value for key, value in exact.items()):
        raise ProbeError("project-cycle admission identity drifted")
    if preview.get("registration_digest") != registration.digest:
        raise ProbeError("project-cycle registration digest drifted")
    if preview.get("constraints_digest") != constraints.digest:
        raise ProbeError("project-cycle constraints digest drifted")
    if preview.get("stage_profiles") != expected_profiles:
        raise ProbeError("project-cycle stage-profile mapping drifted")
    workflow_id = preview.get("workflow_id")
    intake_digest = preview.get("intake_digest")
    if not isinstance(workflow_id, str) or not workflow_id.startswith("cycle-"):
        raise ProbeError("project-cycle ID is invalid")
    if not isinstance(intake_digest, str) or len(intake_digest) != 64:
        raise ProbeError("project-cycle intake digest is invalid")
    return {
        "native_exit": 0,
        "standalone_exit": 0,
        "byte_identical": True,
        "workflow_id": workflow_id,
        "intake_digest": intake_digest,
        "baseline_revision": fixture["baseline"],
        "constraints_digest": constraints.digest,
        "stage_profiles": expected_profiles,
        "pack": exact,
    }


def _exercise_admission(
    root: Path,
    home: Path,
    hermes: str,
    daidala: str,
    env: dict[str, str],
) -> dict[str, Any]:
    fixture = _prepare_admission_fixture(root, home, env)
    nested_env = env.copy()
    nested_env["PATH"] = os.pathsep.join((str(root / "bin"), env.get("PATH", "")))
    nested_env["DAIDALA_PROBE_GITHUB_READ"] = "probe-read-token"
    nested_env["DAIDALA_PROBE_GITHUB_WRITE"] = "probe-write-token"
    common = [
        "project-cycle",
        "admit",
        "--project-manifest",
        str(fixture["manifest"]),
        "--registration",
        str(fixture["registration"]),
        "--issue",
        "42",
        "--default-profile",
        "probe-default",
        "--pack",
        "addyosmani",
    ]
    for stage in WorkflowStage:
        if stage is not WorkflowStage.APPROVAL:
            common.extend(("--stage-profile", f"{stage.value}=probe-{stage.value}"))
    before = _snapshot(fixture["state_paths"])
    standalone_text = run([daidala, *common], env=nested_env)
    after_standalone = _snapshot(fixture["state_paths"])
    if after_standalone != before:
        raise ProbeError("standalone admission preview mutated isolated state")
    native_text = run([hermes, PLUGIN_NAME, *common], env=nested_env)
    after_native = _snapshot(fixture["state_paths"])
    if after_native != before:
        raise ProbeError("native admission preview mutated isolated state")
    result = _validate_admission(native_text, standalone_text, fixture)
    commands = [
        json.loads(line)
        for line in Path(fixture["command_log"]).read_text(encoding="utf-8").splitlines()
    ]
    mutations = [
        command
        for command in commands
        if any(token in command for token in ("send", "create", "comment", "edit"))
    ]
    if mutations:
        raise ProbeError("admission preview crossed a mutation boundary")
    result["state_unchanged"] = True
    result["mutation_commands"] = 0
    return result


def exercise(
    root: Path,
    hermes: str,
    daidala: str,
    expected_host: HostIdentity = SUPPORTED_HOST,
    plugin_directory: Path | None = None,
) -> dict[str, Any]:
    require_isolated_root(root)
    home = root / "home"
    _prepare_home(home, plugin_directory)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env.pop("HERMES_PROFILE", None)
    resolved_hermes = shutil.which(hermes, path=env.get("PATH")) or hermes
    resolved_daidala = shutil.which(daidala, path=env.get("PATH")) or daidala

    version = require_version(run([resolved_hermes, "--version"], env=env), expected_host)
    plugin = _plugin_inventory(resolved_hermes, env)
    packs: dict[str, dict[str, Any]] = {}
    for pack in PACKS:
        native = _validate_pack(
            [resolved_hermes, PLUGIN_NAME, "packs", "validate", pack],
            env,
            f"native {pack} validation",
        )
        standalone = _validate_pack(
            [resolved_daidala, "packs", "validate", pack],
            env,
            f"standalone {pack} validation",
        )
        if native != standalone:
            raise ProbeError(f"native and standalone {pack} validation differ")
        packs[pack] = native
    admission = (
        None
        if plugin_directory is not None
        else _exercise_admission(root, home, resolved_hermes, resolved_daidala, env)
    )

    return {
        "success": True,
        "hermes": version,
        "plugin": {
            "name": PLUGIN_NAME,
            "version": PLUGIN_VERSION,
            "reported": plugin is not None,
            "source": plugin.get("source") if plugin else None,
            "status": plugin.get("status") if plugin else None,
            "discovery": "directory" if plugin_directory else "entrypoint",
        },
        "cli": {
            "native_command": PLUGIN_NAME,
            "standalone_command": Path(resolved_daidala).name,
            "packs": packs,
            "admission_preview": admission,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes", default="hermes", help="Hermes executable to probe")
    parser.add_argument("--daidala", default="daidala", help="Daidala executable to compare")
    parser.add_argument(
        "--plugin-directory",
        type=Path,
        help="Optional directory-plugin source; omit to probe the installed entry point",
    )
    parser.add_argument("--keep-temp", action="store_true", help="Keep the isolated probe root")
    add_expected_host_arguments(parser)
    args = parser.parse_args(argv)
    expected_host = expected_host_from_args(parser, args)
    root = Path(tempfile.mkdtemp(prefix="daidala-plugin-compat-"))
    try:
        result = exercise(
            root,
            args.hermes,
            args.daidala,
            expected_host,
            args.plugin_directory,
        )
        if args.keep_temp:
            result["probe_root"] = str(root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ProbeError, ValueError, json.JSONDecodeError) as error:
        print(f"Hermes plugin compatibility probe failed: {error}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_temp:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
