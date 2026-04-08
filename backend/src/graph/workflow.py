"""
Brand Guardian AI — LangGraph Workflow

Defines the Directed Acyclic Graph (DAG) that orchestrates the compliance audit:

    [START] → [indexer] → [auditor] → [END]
"""

from langgraph.graph import StateGraph, END

from backend.src.graph.state import VideoAuditState
from backend.src.graph.nodes import index_video_node, audit_content_node


def create_graph():
    """Builds and compiles the LangGraph compliance audit workflow."""
    workflow = StateGraph(VideoAuditState)

    workflow.add_node("indexer", index_video_node)
    workflow.add_node("auditor", audit_content_node)

    workflow.set_entry_point("indexer")
    workflow.add_edge("indexer", "auditor")
    workflow.add_edge("auditor", END)

    return workflow.compile()


app = create_graph()
