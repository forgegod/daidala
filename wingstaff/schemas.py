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
    "description": "Create a draft workflow for an absolute local target repository.",
    "parameters": {
        "type": "object",
        "properties": {
            "target_repository": {"type": "string"},
            "goal": {"type": "string"},
            "pack": {"type": "string", "default": "addyosmani"},
            "workflow_id": {"type": "string"},
        },
        "required": ["target_repository", "goal"],
        "additionalProperties": False,
    },
}

STATUS = {
    "name": "wingstaff_status",
    "description": "Return durable workflow state without changing it.",
    "parameters": {
        "type": "object",
        "properties": {"workflow_id": {"type": "string"}},
        "required": ["workflow_id"],
        "additionalProperties": False,
    },
}

VALIDATE = {
    "name": "wingstaff_validate",
    "description": "Validate the workflow pack and clean local Git target baseline.",
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

MODIFY = {
    "name": "wingstaff_modify",
    "description": "Replace the plan artifact and invalidate prior approval.",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string"},
            "path": {"type": "string"},
            "digest": {"type": "string"},
        },
        "required": ["workflow_id", "path", "digest"],
        "additionalProperties": False,
    },
}

CANCEL = {
    "name": "wingstaff_cancel",
    "description": "Cancel a nonterminal workflow with an operator-provided reason.",
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

LIFECYCLE_TOOLS = (START, STATUS, VALIDATE, APPROVE, MODIFY, CANCEL)
ALL_TOOLS = (PACK_INFO, *LIFECYCLE_TOOLS)
