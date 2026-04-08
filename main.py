"""
Brand Guardian AI — CLI Entry Point

Usage:
    uv run python main.py --url "https://youtu.be/YOUR_VIDEO_ID"
    uv run python main.py  # uses AUDIT_VIDEO_URL env var or prompts
"""

import argparse
import json
import logging
import uuid

from dotenv import load_dotenv

load_dotenv(override=True)

from backend.src.graph.workflow import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("brand-guardian-runner")


def run_audit(video_url: str) -> None:
    session_id = str(uuid.uuid4())
    logger.info(f"Starting Audit Session: {session_id}")

    initial_inputs = {
        "video_url": video_url,
        "video_id": f"vid_{session_id[:8]}",
        "compliance_results": [],
        "errors": [],
    }

    print("\n--- Input Payload: INITIALIZING WORKFLOW ---")
    print(json.dumps(initial_inputs, indent=2))

    try:
        final_state = app.invoke(initial_inputs)

        print("\n--- WORKFLOW EXECUTION COMPLETE ---")
        print("\n=== COMPLIANCE AUDIT REPORT ===")
        print(f"Video ID:    {final_state.get('video_id')}")
        print(f"Status:      {final_state.get('final_status')}")

        print("\n[ VIOLATIONS DETECTED ]")
        results = final_state.get("compliance_results", [])
        if results:
            for issue in results:
                print(
                    f"  - [{issue.get('severity')}] "
                    f"{issue.get('category')}: {issue.get('description')}"
                )
        else:
            print("  No violations found.")

        print("\n[ FINAL SUMMARY ]")
        print(final_state.get("final_report"))

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Brand Guardian AI — Video Compliance Auditor")
    parser.add_argument(
        "--url",
        type=str,
        help="YouTube video URL to audit",
    )
    args = parser.parse_args()

    if args.url:
        video_url = args.url
    else:
        import os
        video_url = os.getenv("AUDIT_VIDEO_URL")
        if not video_url:
            video_url = input("Enter YouTube video URL to audit: ").strip()

    if not video_url:
        print("Error: no video URL provided.")
        raise SystemExit(1)

    run_audit(video_url)


if __name__ == "__main__":
    main()
