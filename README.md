# ClaimGuard — AI-Powered Video Compliance Auditing Pipeline

Automatically audits brand video ads against regulatory compliance rules. Submit any YouTube URL and receive a structured violation report in minutes — powered by Azure AI, LangGraph, and GPT-4o.

> **Live demo:** POST `https://your-api/audit` with a YouTube URL → get back a JSON compliance report with violations, severity levels, and a natural language summary.

---

## What It Does

Most brands manually review video ads for compliance — a slow, expensive, and inconsistent process. ClaimGuard eliminates this entirely by:

1. **Downloading** the video from YouTube
2. **Extracting** speech (transcript) and on-screen text (OCR) via Azure Video Indexer
3. **Retrieving** relevant compliance rules from a vector knowledge base (RAG)
4. **Auditing** the content with GPT-4o grounded in those rules
5. **Returning** a structured JSON report with every violation categorized and explained

---

## Architecture

```
YouTube URL
    │
    ▼
[Node 1: Indexer]
  ├── Download video (yt-dlp)
  ├── Upload to Azure Video Indexer
  └── Extract transcript (speech-to-text) + OCR (on-screen text)
    │
    ▼
[Node 2: Auditor]
  ├── Embed transcript → vector similarity search → Azure AI Search
  ├── Retrieve top-k relevant compliance rules (RAG)
  └── GPT-4o analyzes content against retrieved rules
    │
    ▼
Compliance Report (PASS / FAIL + violation list with severity)
```

**Orchestrated as a stateful DAG using LangGraph** — each node reads from and writes to a shared typed state (`VideoAuditState`), making the pipeline fully inspectable, resumable, and extensible.

---

## Key Engineering Highlights

- **Dual-signal extraction** — combines speech-to-text transcript AND OCR on-screen text for complete content coverage, catching violations in both spoken claims and visual text overlays.

- **RAG over compliance documents** — compliance PDFs (FTC guidelines, brand rules, ad specs) are chunked, embedded, and indexed into Azure AI Search. At audit time, the transcript is used as a semantic query to retrieve only the most relevant rules — keeping the LLM prompt focused and accurate.

- **ARM token caching** — Azure management tokens (valid ~60 min) are cached in-process and refreshed only when near expiry, reducing redundant auth API calls by ~95% across long polling sessions.

- **Polling timeout guard** — `wait_for_processing()` enforces a configurable deadline (default 10 min), raising `TimeoutError` instead of polling forever — preventing hung requests in production.

- **Async non-blocking API** — FastAPI endpoint uses `await compliance_graph.ainvoke()`, so the server remains responsive to other requests while a long-running audit is in progress.

- **Module-level singleton clients** — LLM, embeddings, and vector store are initialized once at startup and reused across all requests, eliminating cold-start latency on every API call.

- **Full observability** — Azure Monitor + OpenTelemetry auto-instruments every HTTP request, LLM call, and search query with distributed tracing, latency metrics, and error tracking — zero manual instrumentation needed.

- **Typed state schema** — `VideoAuditState` uses Python `TypedDict` with `Annotated[List, operator.add]` for append-safe list fields (compliance results, errors), preventing accidental overwrites across nodes.

---

## Sample Output

```json
{
  "session_id": "314154a3-84a1-4b42-9e39-1f427d83dbdd",
  "video_id": "vid_314154a3",
  "status": "FAIL",
  "final_report": "The video contains critical violations related to misleading product claims and unauthorized use of a trademarked phrase.",
  "compliance_results": [
    {
      "category": "Claim Validation",
      "severity": "CRITICAL",
      "description": "The claim 'Sunscreen you can't see' could be misleading as it implies invisibility without scientific substantiation."
    },
    {
      "category": "Trademark Usage",
      "severity": "CRITICAL",
      "description": "The phrase 'You can't see me' references a trademarked catchphrase without proper attribution or licensing."
    }
  ]
}
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Workflow orchestration | LangGraph (stateful DAG) |
| LLM | Azure OpenAI (GPT-4o) |
| Embeddings | Azure OpenAI (text-embedding-3-small) |
| Knowledge base | Azure AI Search (vector RAG) |
| Video indexing | Azure Video Indexer (speech-to-text + OCR) |
| API server | FastAPI + Uvicorn (async) |
| Observability | Azure Monitor + OpenTelemetry |
| Auth | Azure DefaultAzureCredential (service principal) |
| Package manager | uv |

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) installed
- Azure subscription with:
  - Azure OpenAI (GPT-4o + text-embedding-3-small deployments)
  - Azure AI Search index
  - Azure Video Indexer account
  - Azure App Registration (service principal with Contributor role on Video Indexer)

---

## Setup

**1. Clone and install dependencies**
```bash
git clone https://github.com/mohitcr77/brand-gaurdian.git
cd brand-gaurdian
uv sync
```

**2. Configure environment variables**
```bash
cp .env.example .env
# Fill in your Azure credentials
```

**3. Index your compliance documents**

Place PDF rule documents in `backend/data/` then run:
```bash
uv run python backend/scripts/index_documents.py
```

---

## Usage

### CLI
```bash
uv run python main.py --url "https://youtu.be/YOUR_VIDEO_ID"
```

### API Server
```bash
uv run uvicorn backend.src.api.server:app --reload
```

```bash
curl -X POST http://localhost:8000/audit \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://youtu.be/YOUR_VIDEO_ID"}'
```

Interactive API docs: `http://localhost:8000/docs`

---

## Environment Variables

| Variable | Description |
|---|---|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_VERSION` | API version (e.g. `2024-12-01-preview`) |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Chat model deployment name (e.g. `gpt-4o`) |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding model deployment name |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_SEARCH_API_KEY` | Azure AI Search admin key |
| `AZURE_SEARCH_INDEX_NAME` | Name of the compliance rules index |
| `AZURE_VI_ACCOUNT_ID` | Video Indexer account ID |
| `AZURE_VI_LOCATION` | Video Indexer region (e.g. `eastus`) |
| `AZURE_VI_NAME` | Video Indexer resource name |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | Azure resource group name |
| `AZURE_TENANT_ID` | Service principal tenant ID |
| `AZURE_CLIENT_ID` | Service principal client ID |
| `AZURE_CLIENT_SECRET` | Service principal client secret |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Azure Monitor connection string (optional) |
| `LANGCHAIN_API_KEY` | LangSmith API key (optional, for tracing) |
| `LANGCHAIN_PROJECT` | LangSmith project name (optional) |

---

## Project Structure

```
├── main.py                          # CLI entry point (--url arg)
├── backend/
│   ├── data/                        # Place compliance rule PDFs here
│   ├── scripts/
│   │   └── index_documents.py       # Chunks + indexes PDFs into Azure AI Search
│   └── src/
│       ├── api/
│       │   ├── server.py            # Async FastAPI server
│       │   └── telemetry.py         # Azure Monitor + OpenTelemetry setup
│       ├── graph/
│       │   ├── nodes.py             # Indexer + Auditor node logic
│       │   ├── state.py             # Typed LangGraph state schema
│       │   └── workflow.py          # DAG definition and compilation
│       └── services/
│           └── video_indexer.py     # Azure Video Indexer client (token caching + timeout)
└── pyproject.toml
```
