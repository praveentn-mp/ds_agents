# Agent Data Fabric

> **Any data source + any MCP tool/server → agent-operable through a unified interface.**

A modular, MCP-native platform where custom connectors, Docker MCP servers, and LangGraph agents work together to provide a universal data & action layer. Non-technical users can query databases, analyze documents, and automate workflows through natural conversation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend (7791)                     │
│  Chat · Connector Hub · MCP Inspector · SQL Explorer · Tools    │
│  Observability Dashboard · Capability Explorer · Settings        │
└───────────────────────┬─────────────────────────────────────────┘
                        │ REST + SSE
┌───────────────────────▼─────────────────────────────────────────┐
│                    FastAPI Backend (7790)                         │
│  Auth/RBAC · Connector Services · Agent Runner · Observability  │
│  LangGraph Orchestrator · RAG Pipeline · SQL Explorer API        │
└──────────┬────────────────────────────┬──────────────────────────┘
           │ Internal HTTP              │ Internal HTTP
┌──────────▼──────────┐    ┌───────────▼──────────────────────────┐
│  MCP Server (7792)  │    │        PostgreSQL (5436)             │
│  FastMCP + SSE      │    │  pgvector · pgcrypto · pg_trgm       │
│  Resources/Tools/   │    │  Operational DB + Vector Store        │
│  Prompts Registry   │    └──────────────────────────────────────┘
└──────────┬──────────┘
           │ Docker SDK
┌──────────▼──────────────────────────────────────────────────────┐
│                   Docker MCP Hub                                 │
│  mcp-filesystem · mcp-browser · mcp-slack · mcp-github          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend API** | FastAPI, Pydantic v2, Uvicorn |
| **Agent Orchestration** | LangGraph, LangChain |
| **LLM** | Azure OpenAI (primary) / Ollama gemma3 (fallback) |
| **RAG** | LlamaIndex, pgvector |
| **Database** | PostgreSQL 16, SQLAlchemy (async), asyncpg |
| **MCP Protocol** | FastMCP, SSE transport |
| **Auth** | JWT (python-jose), bcrypt, Fernet encryption |
| **Docker** | Colima, Docker SDK for Python |
| **Frontend** | React 18, TypeScript 5, Vite 5, Tailwind CSS 3 |
| **State** | Zustand, TanStack Query |

---

## Features

- **Connector Ecosystem** — PostgreSQL, Azure Blob Storage, Filesystem (extensible)
- **Docker MCP Hub** — Run prebuilt MCP servers as Docker containers
- **MCP Inspector** — Inspect resources, tools, prompts, and server status
- **Conversational Agent** — LangGraph-powered multi-agent system with intent classification
- **SQL Explorer** — Execute SQL with Monaco editor, paginated results, query history
- **Custom Tool Builder** — Create, version, and execute sandboxed Python tools
- **RAG Pipeline** — LlamaIndex + pgvector for document search and retrieval
- **Observability** — Token tracking, latency monitoring, execution traces
- **RBAC** — Role-based access control (Admin, Developer, Analyst, Viewer)
- **SSE Streaming** — Real-time trace events and response streaming

---

## Quick Start

### Prerequisites

- **macOS** with Colima or Docker Desktop
- **Python 3.11+**
- **Node.js 18+** and npm
- **PostgreSQL** (managed via Docker in start.sh)

### One-Command Launch

```bash
cd agent-data-fabric
./start.sh
```

This will:
1. Create a Python virtual environment and install dependencies
2. Start PostgreSQL (pgvector) via Docker on port 5436
3. Initialize the database schema and seed data
4. Auto-generate encryption keys (Fernet + JWT)
5. Kill any conflicting processes on configured ports
6. Start the backend API (7790), MCP server (7792), and frontend (7791)

### Access

| Service | URL |
|---|---|
| **Frontend** | http://localhost:7791 |
| **Backend API** | http://localhost:7790 |
| **API Docs (Swagger)** | http://localhost:7790/docs |
| **MCP Server** | http://localhost:7792 |

**Default login:** `admin@adf.local` / `admin123`

---

## Configuration

All settings are in `.env` (auto-created from `.env.example` on first run):

```bash
# LLM — Azure OpenAI (primary)
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_DEPLOYMENT=gpt-4o

# LLM — Ollama (fallback when Azure OpenAI is not configured)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3

# PostgreSQL
POSTGRES_PORT=5436
POSTGRES_DB=agent_data_fabric
POSTGRES_USER=adf_user
POSTGRES_PASSWORD=your-password

# Service ports
BACKEND_PORT=7790
FRONTEND_PORT=7791
MCP_SERVER_PORT=7792
```

---

## Project Structure

```
agent-data-fabric/
├── start.sh                    # One-command launcher
├── docker-compose.yml          # Production orchestration
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
│
├── backend/                    # FastAPI app (port 7790)
│   ├── main.py                 # App factory, CORS, routers
│   ├── config.py               # Pydantic settings
│   ├── database.py             # Async SQLAlchemy
│   ├── api/                    # REST endpoints (11 routers)
│   ├── agents/                 # LangGraph orchestration
│   │   ├── graph.py            # 9-node agent graph
│   │   ├── llm.py              # LLM factory (Azure/Ollama)
│   │   └── nodes/              # Agent nodes
│   ├── connectors/             # Data source connectors
│   ├── mcp/                    # MCP client, registry, Docker hub
│   ├── rag/                    # LlamaIndex RAG pipeline
│   ├── models/                 # SQLAlchemy ORM (16 models)
│   ├── schemas/                # Pydantic schemas
│   ├── services/               # Business logic
│   └── middleware/             # Auth + observability
│
├── mcp_server/                 # Standalone MCP process (port 7792)
│   ├── server.py               # FastMCP with SSE transport
│   └── registry_sync.py        # DB → MCP sync
│
├── frontend/                   # React 18 app (port 7791)
│   └── src/
│       ├── api/                # Typed Axios client
│       ├── store/              # Zustand stores
│       ├── hooks/              # useSSE, custom hooks
│       ├── components/         # Reusable UI components
│       └── pages/              # 9 route-level pages
│
├── db/
│   └── init.sql                # Schema + seeds
│
├── alembic/                    # Database migrations
└── logs/                       # Runtime logs
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/login` | JWT authentication |
| POST | `/auth/register` | User registration |
| GET | `/connectors` | List all connectors |
| POST | `/connectors` | Create connector |
| POST | `/connectors/{id}/test` | Test connection |
| POST | `/connectors/{id}/discover-schema` | Discover schema |
| GET | `/mcp/servers` | List MCP servers |
| POST | `/mcp/servers/{id}/start` | Start MCP container |
| GET | `/mcp/registry/resources` | List MCP resources |
| GET | `/mcp/registry/tools` | List MCP tools |
| GET | `/mcp/registry/prompts` | List MCP prompts |
| POST | `/chat` | Chat with agent (SSE) |
| GET | `/tools` | List custom tools |
| POST | `/tools/{id}/execute` | Execute tool |
| POST | `/sql/execute` | Run SQL query |
| GET | `/observability/summary` | Token & latency stats |
| GET | `/capabilities` | All system capabilities |
| GET | `/health` | Health check |

---

## Agent Graph

The LangGraph agent uses a 9-node decision graph:

```
User Input → classify_intent → resolve_capabilities
                                     ↓
                              route_decision
                            /      |       \
                     query_agent  tool_agent  rag_agent
                            \      |       /
                          response_formatter → Done
```

**Intent categories:** `query` | `tool` | `hybrid` | `rag` | `build_connector` | `build_tool`

---

## MCP Primitives

### Resources
- `connector://postgres/{table}` — Live queryable table
- `connector://azure_blob/{container}` — Blob storage
- `mcp://filesystem/{path}` — Local filesystem

### Tools
- **QueryResource** — Query any connector resource
- **WriteResource** — Write to any connector
- **MCPToolCall** — Proxy to Docker MCP servers
- **CreateConnector** — Build new connectors
- **CreateTool** — Build custom tools

### Prompts
- `tool_selector` — Select best tools for intent
- `connector_vs_tool_decider` — Route: data vs capability path
- `query_planner` — Multi-step query decomposition
- `mcp_server_selector` — Pick Docker MCP server

---

## RBAC Permissions

| Permission | Admin | Developer | Analyst | Viewer |
|---|:---:|:---:|:---:|:---:|
| manage_users | ✓ | — | — | — |
| manage_connectors | ✓ | ✓ | — | — |
| manage_tools | ✓ | ✓ | — | — |
| execute_sql_write | ✓ | ✓ | — | — |
| execute_sql_read | ✓ | ✓ | ✓ | — |
| query_data | ✓ | ✓ | ✓ | ✓ |
| view_traces | ✓ | ✓ | ✓ | — |

---

## Docker Compose (Production)

```bash
# Build and run all services
docker compose up -d

# View logs
docker compose logs -f backend
```

---

## Development

```bash
# Backend only
source venv/bin/activate
uvicorn backend.main:app --reload --port 7790

# Frontend only
cd frontend && npm run dev

# MCP Server only
python -m mcp_server.server
```

---

## License

Private — All rights reserved.
