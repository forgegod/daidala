# Repository agent skills

## Purpose

Own optional, versioned agent playbooks that contributors can reuse across projects.

## Ownership

| Path                    | Owns                                                         |
| ----------------------- | ------------------------------------------------------------ |
| `software-development/` | Product-record, capability-wireframe, and migration playbooks. |

## Local Contracts

- A skill is an execution aid, not a source of product behaviour, progress, or architectural authority.
- Durable product policy lives in each adopting project's contributor instructions and owning documentation contracts. A portable skill may define a canonical artifact layout and lifecycle, but not project-specific behaviour or policy.
- Skills follow the Agent Skills `SKILL.md` format and remain safe to read without a Hermes installation.
- Do not add credentials, profile-local paths, or agent-private state to repository skills.

## Work Guidance

Add a skill only when it provides a reusable, checkable procedure beyond a project's local contracts. Keep project-specific behaviour, commands, and lifecycle exceptions in the adopting project; a portable skill may define stable names, paths, and lifecycle rules. Keep generic planning mechanics in the shared `phased-plan-*` skills.

## Verification

Run the adopting project's declared documentation and record checks, validate changed Markdown links, and read the resulting `SKILL.md` frontmatter and completion criteria. A fresh Hermes session with this checkout configured as an external skill directory is the integration probe.

## Child DOX Index

| Child                            | Owns                                          | Read when editing…                                     |
| -------------------------------- | --------------------------------------------- | ------------------------------------------------------ |
| `software-development/AGENTS.md` | Product-record workflow and migration skills. | Capability/change-record workflows or their migration. |

Parent contract: `../AGENTS.md`.
