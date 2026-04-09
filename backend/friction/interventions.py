"""Friction UI payload definitions.

The copy here is carefully worded — it gets shown to real customers in a
moment of high stress. Any changes need product/legal sign-off.
"""

FRICTION_TYPES: dict[str, dict] = {
    "awareness_prompt": {
        "ui_component": "banner",
        "heading": "Quick check before you send",
        "body": (
            "Are you currently on a call with anyone — including someone "
            "claiming to be from your bank?"
        ),
        "buttons": ["No, proceed", "Yes, I'm on a call"],
        "on_yes": "show_scam_warning_and_abort",
        "on_no": "allow_proceed",
    },
    "cooling_timer": {
        "ui_component": "blocking_overlay",
        "duration_seconds": 600,
        "heading": "We've added a short pause",
        "body": (
            "For your protection, we pause large transfers when we notice "
            "unusual session activity. This transfer will be ready in:"
        ),
        "show_scam_facts": True,
        "cancellable": True,
    },
    "callback_required": {
        "ui_component": "full_block",
        "heading": "Transfer held for your safety",
        "body": (
            "We need to verify this transfer. We'll call you at the number on "
            "file within 15 minutes."
        ),
        "cancellable": True,
    },
}
