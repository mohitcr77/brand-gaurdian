import operator
from typing import Annotated, List, Dict, Optional, Any, TypedDict


class ComplianceIssue(TypedDict):
    category: str            # e.g., "FTC_DISCLOSURE", "Claim Validation"
    description: str         # Specific detail of the violation
    severity: str            # "CRITICAL" | "WARNING"
    timestamp: Optional[str] # Timestamp of occurrence (if applicable)


class VideoAuditState(TypedDict):
    """
    Defines the data schema for the LangGraph execution context.
    Acts as the single source of truth passed between all nodes.
    """
    # --- Input Parameters ---
    video_url: str
    video_id: str

    # --- Ingestion & Extraction Data ---
    local_file_path: Optional[str]
    video_metadata: Dict[str, Any]  # e.g., {"duration": 15, "platform": "youtube"}
    transcript: Optional[str]       # Full extracted speech-to-text
    ocr_text: List[str]             # List of recognized on-screen text strings

    # --- Analysis Output ---
    # Annotated with operator.add to allow append-only updates from multiple nodes
    compliance_results: Annotated[List[ComplianceIssue], operator.add]

    # --- Final Deliverables ---
    final_status: str   # "PASS" | "FAIL"
    final_report: str   # Natural language summary for the frontend

    # --- System Observability ---
    # Appends errors without halting execution
    errors: Annotated[List[str], operator.add]
