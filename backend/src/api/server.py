"""
Brand Guardian AI — FastAPI Server

Run with:
    uv run uvicorn backend.src.api.server:app --reload

Endpoints:
    POST /audit   — Submit a video URL for compliance auditing
    GET  /health  — Health check
"""

import uuid
import logging

from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

from backend.src.api.telemetry import setup_telemetry
from backend.src.graph.workflow import app as compliance_graph

setup_telemetry()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-server")

app = FastAPI(
    title="Brand Guardian AI",
    description="Audits video content against brand compliance rules using Azure AI + LangGraph.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class AuditRequest(BaseModel):
    video_url: str


class ComplianceIssue(BaseModel):
    category: str
    severity: str
    description: str


class AuditResponse(BaseModel):
    session_id: str
    video_id: str
    status: str
    final_report: str
    compliance_results: List[ComplianceIssue]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/audit", response_model=AuditResponse)
async def audit_video(request: AuditRequest):
    """
    Submit a YouTube video URL for brand compliance auditing.
    Runs the full LangGraph pipeline: Download → Index → Audit.
    """
    session_id = str(uuid.uuid4())
    video_id = f"vid_{session_id[:8]}"

    logger.info(f"Audit request received — session={session_id} url={request.video_url}")

    initial_inputs = {
        "video_url": request.video_url,
        "video_id": video_id,
        "compliance_results": [],
        "errors": [],
    }

    try:
        # ainvoke is non-blocking — server can handle other requests while this runs
        final_state = await compliance_graph.ainvoke(initial_inputs)

        return AuditResponse(
            session_id=session_id,
            video_id=final_state.get("video_id", video_id),
            status=final_state.get("final_status", "UNKNOWN"),
            final_report=final_state.get("final_report", "No report generated."),
            compliance_results=final_state.get("compliance_results", []),
        )

    except Exception as e:
        logger.error(f"Audit failed — session={session_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    """Returns service health status."""
    return {"status": "healthy", "service": "Brand Guardian AI"}
