"""Hermes-visible JSON tool schemas."""

PACK_INFO = {
    "name": "wingstaff_pack_info",
    "description": (
        "Load and validate a Wingstaff software-development workflow pack. "
        "Use this before starting a workflow to confirm its lifecycle and external skills."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pack": {
                "type": "string",
                "description": "Bundled pack name. The bootstrap includes 'addyosmani'.",
                "default": "addyosmani",
            }
        },
        "additionalProperties": False,
    },
}
