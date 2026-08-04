from typing import Any, Dict

def get_mock_notification_result(recipient: str) -> Dict[str, Any]:
    """
    Returns mock email / channel notification delivery logs.
    """
    return {
        "delivered": True,
        "dispatch_channel": "Email / SMTP",
        "recipient": recipient,
        "message_id": "msg-987654321"
    }
