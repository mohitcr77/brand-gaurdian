import json
import os
import logging
import re
from typing import Dict, Any

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.messages import SystemMessage, HumanMessage

from backend.src.graph.state import VideoAuditState, ComplianceIssue
from backend.src.services.video_indexer import VideoIndexerService

logger = logging.getLogger("brand-guardian")

# ---------------------------------------------------------------------------
# Module-level singletons — initialized once at startup, reused on every call
# ---------------------------------------------------------------------------

_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
    openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    temperature=0.0,
)

_embeddings = AzureOpenAIEmbeddings(
    azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
    openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

_vector_store = AzureSearch(
    azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    azure_search_key=os.getenv("AZURE_SEARCH_API_KEY"),
    index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
    embedding_function=_embeddings.embed_query,
)


# ---------------------------------------------------------------------------
# NODE 1: INDEXER
# ---------------------------------------------------------------------------

def index_video_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Downloads a YouTube video, uploads it to Azure Video Indexer,
    waits for processing, and returns the extracted transcript + OCR data.
    """
    video_url = state.get("video_url")
    video_id_input = state.get("video_id", "vid_demo")

    logger.info(f"--- [Node: Indexer] Processing: {video_url} ---")

    local_filename = "temp_audit_video.mp4"

    try:
        vi_service = VideoIndexerService()

        # 1. Download
        if "youtube.com" in video_url or "youtu.be" in video_url:
            local_path = vi_service.download_youtube_video(video_url, output_path=local_filename)
        else:
            raise ValueError("Only YouTube URLs are supported.")

        # 2. Upload
        azure_video_id = vi_service.upload_video(local_path, video_name=video_id_input)
        logger.info(f"Upload Success. Azure ID: {azure_video_id}")

        # 3. Cleanup local file
        if os.path.exists(local_path):
            os.remove(local_path)

        # 4. Wait for Azure processing
        raw_insights = vi_service.wait_for_processing(azure_video_id)

        # 5. Extract structured data
        clean_data = vi_service.extract_data(raw_insights)

        logger.info("--- [Node: Indexer] Extraction Complete ---")
        return clean_data

    except Exception as e:
        logger.error(f"Video Indexer Failed: {e}")
        return {
            "errors": [str(e)],
            "final_status": "FAIL",
            "transcript": "",
            "ocr_text": [],
        }


# ---------------------------------------------------------------------------
# NODE 2: COMPLIANCE AUDITOR
# ---------------------------------------------------------------------------

def audit_content_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Performs Retrieval-Augmented Generation (RAG) to audit video content
    against brand compliance rules stored in Azure AI Search.
    """
    logger.info("--- [Node: Auditor] Querying Knowledge Base & LLM ---")

    transcript = state.get("transcript", "")

    if not transcript:
        logger.warning("No transcript available. Skipping audit.")
        return {
            "final_status": "FAIL",
            "final_report": "Audit skipped: video processing failed (no transcript).",
        }

    # RAG: retrieve relevant compliance rules
    ocr_text = state.get("ocr_text", [])
    query_text = f"{transcript} {' '.join(ocr_text)}"
    docs = _vector_store.similarity_search(query_text, k=3)
    retrieved_rules = "\n\n".join([doc.page_content for doc in docs])

    system_prompt = f"""
You are a Senior Brand Compliance Auditor.

OFFICIAL REGULATORY RULES:
{retrieved_rules}

INSTRUCTIONS:
1. Analyze the transcript and on-screen text (OCR) provided below.
2. Identify ANY violations of the rules above.
3. Return STRICTLY valid JSON in the following format — no markdown, no extra text:

{{
    "compliance_results": [
        {{
            "category": "Claim Validation",
            "severity": "CRITICAL",
            "description": "Explanation of the violation..."
        }}
    ],
    "status": "FAIL",
    "final_report": "Summary of findings..."
}}

If no violations are found, set "status" to "PASS" and "compliance_results" to [].
"""

    user_message = f"""
VIDEO METADATA: {state.get('video_metadata', {})}
TRANSCRIPT: {transcript}
ON-SCREEN TEXT (OCR): {ocr_text}
"""

    try:
        response = _llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        content = response.content
        # Strip markdown code fences if present
        if "```" in content:
            match = re.search(r"```(?:json)?([\s\S]*?)```", content, re.DOTALL)
            if match:
                content = match.group(1)

        audit_data = json.loads(content.strip())

        return {
            "compliance_results": audit_data.get("compliance_results", []),
            "final_status": audit_data.get("status", "FAIL"),
            "final_report": audit_data.get("final_report", "No report generated."),
        }

    except Exception as e:
        logger.error(f"Auditor Node Error: {e}")
        logger.error(f"Raw LLM Response: {response.content if 'response' in locals() else 'None'}")
        return {
            "errors": [str(e)],
            "final_status": "FAIL",
        }
