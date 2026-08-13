"""Hermes-visible JSON tool schemas."""

PACK_INFO = {
    "name": "daidala_pack_info",
    "description": "Load and validate an installed Daidala workflow pack.",
    "parameters": {
        "type": "object",
        "properties": {
            "pack": {
                "type": "string",
                "description": "Bundled pack name.",
                "default": "addyosmani",
            }
        },
        "additionalProperties": False,
    },
}

START = {
    "name": "daidala_start",
    "description": "Create a validated policy ledger for one named Kanban board.",
    "parameters": {
        "type": "object",
        "properties": {
            "board_slug": {"type": "string"},
            "target_repository": {"type": "string"},
            "goal": {"type": "string"},
            "stage_profiles": {
                "type": "object",
                "properties": {
                    stage: {"type": "string"}
                    for stage in (
                        "define",
                        "plan",
                        "implement",
                        "verify",
                        "review",
                        "deliver",
                    )
                },
                "required": [
                    "define",
                    "plan",
                    "implement",
                    "verify",
                    "review",
                    "deliver",
                ],
                "additionalProperties": False,
            },
            "pack": {"type": "string", "default": "addyosmani"},
            "workflow_id": {"type": "string"},
            "constraints_content": {"type": "string"},
            "constraints_skill": {"type": "string"},
            "constraints_skill_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
        "required": [
            "board_slug",
            "target_repository",
            "goal",
            "stage_profiles",
            "workflow_id",
        ],
        "additionalProperties": False,
    },
}

START_FROM_PLAN = {
    "name": "daidala_start_from_plan",
    "description": "Preview or admit one Git-pinned pending repository plan phase.",
    "parameters": {
        "type": "object",
        "properties": {
            "board_slug": {"type": "string"},
            "target_repository": {"type": "string"},
            "plan_path": {"type": "string"},
            "source_revision": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "phase_number": {"type": "integer", "minimum": 0},
            "stage_profiles": {
                "type": "object",
                "properties": {
                    stage: {"type": "string"}
                    for stage in (
                        "define",
                        "plan",
                        "implement",
                        "verify",
                        "review",
                        "deliver",
                    )
                },
                "required": [
                    "define",
                    "plan",
                    "implement",
                    "verify",
                    "review",
                    "deliver",
                ],
                "additionalProperties": False,
            },
            "pack": {"type": "string", "default": "addyosmani"},
            "workflow_id": {"type": "string"},
            "predecessor_workflow_id": {"type": ["string", "null"]},
            "constraints_content": {"type": "string"},
            "constraints_skill": {"type": "string"},
            "constraints_skill_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "apply": {"type": "boolean", "default": False},
            "expected_preview_digest": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
        },
        "required": [
            "board_slug",
            "target_repository",
            "plan_path",
            "source_revision",
            "phase_number",
            "stage_profiles",
            "workflow_id",
        ],
        "additionalProperties": False,
    },
}

REPLACE_CONSTRAINTS = {
    "name": "daidala_replace_constraints",
    "description": "Replace workflow constraints from explicit content or an exact policy skill.",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "expected_current_digest": {
                "type": ["string", "null"],
                "pattern": "^[0-9a-f]{64}$",
            },
            "constraints_content": {"type": "string"},
            "constraints_skill": {"type": "string"},
            "constraints_skill_digest": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
        },
        "required": ["workflow_id", "expected_current_digest"],
        "additionalProperties": False,
    },
}

STATUS = {
    "name": "daidala_status",
    "description": "Return policy facts beside live, read-only Kanban card status.",
    "parameters": {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    },
}

CHECKOUTS_STATUS = {
    "name": "daidala_checkouts_status",
    "description": (
        "Report checkout status without refreshing, adopting, pruning, or changing policy."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

APPROVE = {
    "name": "daidala_approve",
    "description": "Approve the exact current plan digest for implementation.",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "plan_digest": {"type": "string"},
        },
        "required": ["workflow_id", "plan_digest"],
        "additionalProperties": False,
    },
}

CANCEL = {
    "name": "daidala_cancel",
    "description": "Clean up Daidala-owned worktree state before Kanban archival.",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["workflow_id", "reason"],
        "additionalProperties": False,
    },
}

SUBMIT_ARTIFACT = {
    "name": "daidala_submit_artifact",
    "description": "Store and validate a definition or plan artifact.",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "stage": {"type": "string", "enum": ["define", "plan"]},
            "content": {"type": "string"},
            "approval_summary": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string", "minLength": 1, "maxLength": 200},
                    "changes": {
                        "type": "array", "minItems": 1, "maxItems": 12,
                        "items": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                    "affected_areas": {
                        "type": "array", "minItems": 0, "maxItems": 12,
                        "items": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                    "risks": {
                        "type": "array", "minItems": 0, "maxItems": 12,
                        "items": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                    "verification": {
                        "type": "array", "minItems": 1, "maxItems": 12,
                        "items": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                },
                "required": [
                    "headline", "changes", "affected_areas", "risks", "verification",
                ],
                "additionalProperties": False,
            },
        },
        "required": ["workflow_id", "stage", "content"],
        "additionalProperties": False,
    },
}

REVIEW_SUMMARY = SUBMIT_ARTIFACT["parameters"]["properties"]["approval_summary"]
REVIEW_FINDING = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "pattern": "^[a-z][a-z0-9-]{0,63}$"},
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "blocking": {"type": "boolean"},
        "title": {"type": "string", "minLength": 1, "maxLength": 200},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 2000},
        "evidence_digests": {
            "type": "array", "minItems": 1, "maxItems": 8,
            "items": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "uniqueItems": True,
        },
    },
    "required": ["id", "severity", "blocking", "title", "rationale", "evidence_digests"],
    "additionalProperties": False,
}
SUBMIT_REVIEW = {
    "name": "daidala_submit_review",
    "description": (
        "Record structured review evidence bound to current implementation and verification."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "outcome": {"type": "string", "enum": ["accepted", "changes_requested", "rejected"]},
            "summary": REVIEW_SUMMARY,
            "findings": {"type": "array", "maxItems": 32, "items": REVIEW_FINDING},
        },
        "required": ["workflow_id", "outcome", "summary", "findings"],
        "additionalProperties": False,
    },
}
REVIEW_DISPOSITION = {
    "name": "daidala_review_disposition",
    "description": "Record an attended disposition for the exact current review.",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "review_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "action": {
                "type": "string",
                "enum": ["accept_delivery", "request_revision", "reject_workflow"],
            },
            "actor": {"type": "string", "minLength": 1, "maxLength": 200},
            "rationale": {"type": "string", "minLength": 1, "maxLength": 2000},
        },
        "required": ["workflow_id", "review_digest", "action", "actor", "rationale"],
        "additionalProperties": False,
    },
}

PREPARE_IMPLEMENTATION = {
    "name": "daidala_prepare_implementation",
    "description": "Create the exact-approved Daidala implementation worktree.",
    "parameters": {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    },
}

CAPTURE_IMPLEMENTATION = {
    "name": "daidala_capture_implementation",
    "description": "Capture the implementation worktree diff for verification.",
    "parameters": {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    },
}

RECORD_VERIFICATION = {
    "name": "daidala_record_verification",
    "description": "Persist command output and structured verification evidence.",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "command": {"type": "string"},
            "exit_code": {"type": "integer"},
            "output": {"type": "string"},
        },
        "required": ["workflow_id", "command", "exit_code", "output"],
        "additionalProperties": False,
    },
}

RECORD_SKILL_ACTIVATION = {
    "name": "daidala_record_skill_activation",
    "description": "Validate and persist this stage worker's skill activation decisions.",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "stage": {
                "type": "string",
                "enum": ["define", "plan", "implement", "verify", "review", "deliver"],
            },
            "supersedes_digest": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
            "decisions": {
                "type": "array", "minItems": 1, "maxItems": 32,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 128,
                            "pattern": "^[a-z0-9][a-z0-9-]{0,127}$",
                        },
                        "category": {
                            "type": "string",
                            "enum": [
                                "applicable",
                                "deferred",
                                "not_applicable",
                                "blocked",
                            ],
                        },
                        "rank": {"type": ["integer", "null"], "minimum": 1, "maximum": 32},
                        "matched_criteria": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 8,
                            "items": {"type": "string", "minLength": 1, "maxLength": 500},
                        },
                        "evidence": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 8,
                            "items": {"type": "string", "minLength": 1, "maxLength": 500},
                        },
                        "rationale": {"type": "string", "minLength": 1, "maxLength": 1000},
                        "condition": {"type": ["string", "null"], "minLength": 1, "maxLength": 500},
                    },
                    "required": [
                        "name",
                        "category",
                        "rank",
                        "matched_criteria",
                        "evidence",
                        "rationale",
                        "condition",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["workflow_id", "stage", "supersedes_digest", "decisions"],
        "additionalProperties": False,
    },
}

LIFECYCLE_TOOLS = (
    START,
    START_FROM_PLAN,
    STATUS,
    CHECKOUTS_STATUS,
    REPLACE_CONSTRAINTS,
    APPROVE,
    CANCEL,
)
EXECUTION_TOOLS = (
    SUBMIT_ARTIFACT,
    SUBMIT_REVIEW,
    PREPARE_IMPLEMENTATION,
    CAPTURE_IMPLEMENTATION,
    RECORD_SKILL_ACTIVATION,
    RECORD_VERIFICATION,
)
ALL_TOOLS = (PACK_INFO, *LIFECYCLE_TOOLS, REVIEW_DISPOSITION, *EXECUTION_TOOLS)
