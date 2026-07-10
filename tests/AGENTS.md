# tests/

## Purpose

Prove the deterministic pack model, Hermes plugin registration contract, and packaged-resource completeness without touching a real Hermes profile.

## Ownership

- Unit tests for pack loading and validation.
- Fake-context tests for plugin tool and skill registration.
- Build/install smoke tests as the package matures.

## Local Contracts

- Tests must not mutate `~/.hermes`, start a gateway, use network services, or call a live model.
- Use real package resources and temporary files; mock only the Hermes host boundary.

## Work Guidance

- Every new state transition requires positive, invalid-transition, and persistence tests.
- Every new packaged resource requires a wheel-content assertion.

## Verification

```bash
pytest
```

## Child DOX Index

*(empty — `tests/` is a flat leaf.)*

See [`/AGENTS.md`](../AGENTS.md).
