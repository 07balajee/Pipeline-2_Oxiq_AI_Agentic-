from typing import Any, Dict

def get_mock_document_packet(workflow_id: str) -> Dict[str, Any]:
    """
    Returns mock compiled document packet details.
    """
    return {
        "packet_id": f"doc-{workflow_id[:6]}",
        "document_url": f"files/packets/interview_packet_{workflow_id[:8]}.pdf",
        "summary": "Consolidated candidate interview scheduling and initial profile screening summary packet."
    }
