def get_mock_meet_url(workflow_id: str) -> str:
    """
    Generates mock virtual meeting access urls.
    """
    return f"https://meet.google.com/mock-{workflow_id[:8]}"
