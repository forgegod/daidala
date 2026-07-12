"""Hermes-visible JSON tool schemas."""

PACK_INFO = {
    "name": "wingstaff_pack_info",
    "description": "Load and validate an installed Wingstaff workflow pack.",
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
    "name": "wingstaff_start",
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

REPLACE_CONSTRAINTS = {
    "name": "wingstaff_replace_constraints",
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
    "name": "wingstaff_status",
    "description": "Return policy facts beside live, read-only Kanban card status.",
    "parameters": {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    },
}

APPROVE = {
    "name": "wingstaff_approve",
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
    "name": "wingstaff_cancel",
    "description": "Clean up Wingstaff-owned worktree state before Kanban archival.",
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
    "name": "wingstaff_submit_artifact",
    "description": "Store and validate a definition, plan, or review artifact.",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "stage": {"type": "string", "enum": ["define", "plan", "review"]},
            "content": {"type": "string"},
        },
        "required": ["workflow_id", "stage", "content"],
        "additionalProperties": False,
    },
}

PREPARE_IMPLEMENTATION = {
    "name": "wingstaff_prepare_implementation",
    "description": "Create the exact-approved Wingstaff implementation worktree.",
    "parameters": {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    },
}

CAPTURE_IMPLEMENTATION = {
    "name": "wingstaff_capture_implementation",
    "description": "Capture the implementation worktree diff for verification.",
    "parameters": {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    },
}

RECORD_VERIFICATION = {
    "name": "wingstaff_record_verification",
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
    "name": "wingstaff_record_skill_activation",
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

DELIVER = {
    "name": "wingstaff_deliver",
    "description": "Record reviewed paths and evidence without commit or push.",
    "parameters": {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    },
}

LIFECYCLE_TOOLS = (START, STATUS, REPLACE_CONSTRAINTS, APPROVE, CANCEL)
EXECUTION_TOOLS = (
    SUBMIT_ARTIFACT,
    PREPARE_IMPLEMENTATION,
    CAPTURE_IMPLEMENTATION,
    RECORD_SKILL_ACTIVATION,
    RECORD_VERIFICATION,
    DELIVER,
)
ALL_TOOLS = (PACK_INFO, *LIFECYCLE_TOOLS, *EXECUTION_TOOLS)
