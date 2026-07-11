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
            "pack": {"type": "string", "default": "addyosmani"},
            "workflow_id": {"type": "string"},
        },
        "required": ["board_slug", "target_repository", "goal"],
        "additionalProperties": False,
    },
}

STATUS = {
    "name": "wingstaff_status",
    "description": "Return Wingstaff policy facts without copying Kanban status.",
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
    "description": "Store a definition, plan, or review artifact and advance state.",
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

LIFECYCLE_TOOLS = (START, STATUS, APPROVE, CANCEL)
EXECUTION_TOOLS = (
    SUBMIT_ARTIFACT,
    PREPARE_IMPLEMENTATION,
    CAPTURE_IMPLEMENTATION,
    RECORD_VERIFICATION,
    DELIVER,
)
ALL_TOOLS = (PACK_INFO, *LIFECYCLE_TOOLS, *EXECUTION_TOOLS)
