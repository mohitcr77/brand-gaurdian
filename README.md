# Brand Guardian AI

An AI-powered video compliance auditing pipeline that automatically checks brand videos against regulatory rules. Submit a YouTube URL and receive a detailed compliance report — powered by Azure AI, LangGraph, and GPT-4o.

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
  ├── Embed transcript → query Azure AI Search (RAG)
  ├── Retrieve relevant compliance rules
  └── Send to GPT-4o for violation analysis
    │
    ▼
Compliance Report (PASS / FAIL + violations list)
```

## Tech Stack

| Component | Technology |
|---|---|
| Workflow orchestration | LangGraph |
| LLM | Azure OpenAI (GPT-4o) |
| Embeddings | Azure OpenAI (text-embedding-3-small) |
| Knowledge base | Azure AI Search (vector RAG) |
| Video indexing | Azure Video Indexer |
| API server | FastAPI + Uvicorn |
| Observability | Azure Monitor + OpenTelemetry |
| Package manager | uv |

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) installed
- Azure subscription with the following resources provisioned:
  - Azure OpenAI (GPT-4o + text-embedding-3-small deployments)
  - Azure AI Search index
  - Azure Video Indexer account
  - Azure App Registration (service principal)

## Setup

**1. Clone and install dependencies**
```bash
git clone https://github.com/mohitcr77/brand-gaurdian.git
cd brand-gaurdian
uv sync
```

**2. Configure environment variables**

Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

**3. Index your compliance documents**

Place PDF rule documents in `backend/data/` then run:
```bash
uv run python backend/scripts/index_documents.py
```

## Usage

### CLI
```bash
uv run python main.py --url "https://youtu.be/YOUR_VIDEO_ID"
```

Or via environment variable:
```bash
AUDIT_VIDEO_URL="https://youtu.be/YOUR_VIDEO_ID" uv run python main.py
```

### API Server
```bash
uv run uvicorn backend.src.api.server:app --reload
```

Send a request:
```bash
curl -X POST http://localhost:8000/audit \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://youtu.be/YOUR_VIDEO_ID"}'
```

Interactive API docs: `http://localhost:8000/docs`

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
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Azure Monitor connection string |
| `LANGCHAIN_API_KEY` | LangSmith API key (optional, for tracing) |
| `LANGCHAIN_PROJECT` | LangSmith project name (optional) |

## Project Structure

```
├── main.py                          # CLI entry point
├── backend/
│   ├── data/                        # Place compliance rule PDFs here
│   ├── scripts/
│   │   └── index_documents.py       # Indexes PDFs into Azure AI Search
│   └── src/
│       ├── api/
│       │   ├── server.py            # FastAPI server
│       │   └── telemetry.py         # Azure Monitor setup
│       ├── graph/
│       │   ├── nodes.py             # Indexer + Auditor node logic
│       │   ├── state.py             # LangGraph state schema
│       │   └── workflow.py          # DAG definition
│       └── services/
│           └── video_indexer.py     # Azure Video Indexer client
└── pyproject.toml
```
