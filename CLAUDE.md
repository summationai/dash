# CLAUDE.md

## Project Overview

Dash is a self-learning data agent that delivers **insights, not just SQL results**. Built on the [Agno](https://github.com/agno-agi/agno) framework (open-source agent toolkit). It grounds SQL generation in 6 layers of context and improves automatically with every query. Inspired by [OpenAI's in-house data agent](https://openai.com/index/inside-our-in-house-data-agent/).

Currently running against **TPC-H SF1** data in DuckDB (8 tables, ~8M rows).

## Structure

```
dash/
├── agents.py             # Agent config: models, tools, learning, instructions
├── paths.py              # Path constants
├── knowledge/            # Knowledge files (tables, queries, business rules)
│   ├── tables/           # Table metadata JSON files
│   ├── queries/          # Validated SQL queries
│   └── business/         # Business rules and metrics
├── context/
│   ├── semantic_model.py # Layer 1: Table usage
│   └── business_rules.py # Layer 2: Business rules
├── tools/
│   ├── introspect.py     # Runtime schema inspection
│   ├── save_query.py     # Save validated queries to knowledge
│   ├── save_learning.py  # Save learnings with verification
│   └── export_excel.py   # Export query results to formatted .xlsx
├── scripts/
│   ├── load_data.py      # Load F1 sample data (PostgreSQL)
│   └── load_knowledge.py # Load knowledge files into vector DB
└── evals/
    ├── test_cases.py     # TPC-H test cases with golden SQL (18 cases)
    ├── grader.py         # LLM-based response grader
    └── run_evals.py      # Eval runner (string match / LLM grade / result compare)

app/
├── main.py               # API entry point (AgentOS → FastAPI)
└── config.yaml           # Agent configuration

db/
├── session.py            # PostgreSQL session factory
├── url.py                # PostgreSQL URL builder
└── duckdb_url.py         # DuckDB URL builder
```

## Local Setup

### Prerequisites
- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- PostgreSQL with pgvector extension
- API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` in `.env`

### First-time setup

```bash
# 1. Venv + dependencies
./scripts/venv_setup.sh && source .venv/bin/activate

# 2. Create PostgreSQL database (needed for knowledge + agent state)
psql postgres -c "CREATE ROLE ai WITH LOGIN PASSWORD 'ai' SUPERUSER;"
psql postgres -c "CREATE DATABASE ai OWNER ai;"
psql -U ai -d ai -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 3. Generate TPC-H data (DuckDB)
python -c "
import duckdb
con = duckdb.connect('data/tpch_sf1.db')
con.execute('INSTALL tpch; LOAD tpch; CALL dbgen(sf=1);')
con.close()
"

# 4. Load knowledge into vector DB
set -a && source .env && set +a
python -m dash.scripts.load_knowledge

# 5. Set DuckDB path (add to .env or export)
export DUCKDB_PATH=$(pwd)/data/tpch_sf1.db
```

### Running

```bash
# Always load env first
source .venv/bin/activate && set -a && source .env && set +a
export DUCKDB_PATH=$(pwd)/data/tpch_sf1.db

python -m dash                     # CLI mode (interactive)
python -m dash.agents              # Quick test (single query)
./scripts/format.sh                # Format code
./scripts/validate.sh              # Lint + type check
```

### Evaluations

```bash
python -m dash.evals.run_evals              # All 18 TPC-H tests (string matching)
python -m dash.evals.run_evals -c basic     # Category: basic|aggregation|data_quality|complex|edge_case
python -m dash.evals.run_evals -v           # Verbose (show responses on failure)
python -m dash.evals.run_evals -g           # LLM grader mode
python -m dash.evals.run_evals -r           # Compare against golden SQL results
python -m dash.evals.run_evals -g -r -v     # All modes combined
```

Last full eval: **17/18 (94%)** — the 1 failure is a string matching false positive.

## Architecture

### What Agno provides

Agno is the orchestration framework. Dash configures it.

| Agno component | Role in Dash |
|---|---|
| `Agent` | Runs the LLM loop (think → call tools → respond) |
| `Claude` | Model abstraction (Opus 4.5 for agent, Sonnet 4.5 for learning extraction) |
| `Knowledge` + `PgVector` | Vector store with hybrid search (semantic + keyword) in PostgreSQL |
| `LearningMachine` | Auto-extracts learnings from conversations, provides search/save tools |
| `@tool` decorator | Turns Python functions into agent-callable tools |
| `SQLTools` | Built-in SQL execution against DuckDB |
| `MCPTools` | MCP protocol (Exa web search) |
| `PostgresDb` | Stores chat history, agent runs, knowledge contents |
| `AgentOS` | Wraps agents into FastAPI app |

### Two Knowledge Systems

| System | Storage | Mode | Purpose |
|--------|---------|------|---------|
| **Knowledge** (`dash_knowledge`) | `dash_knowledge` + `dash_knowledge_contents` tables | Searched automatically | Curated: table schemas, validated queries, business rules |
| **Learnings** (`dash_learnings`) | `dash_learnings` + `dash_learnings_contents` tables | ALWAYS mode (auto-extract) | Dynamic: error patterns, type gotchas, user corrections |

### Tools

| Tool | File | What it does |
|------|------|-------------|
| `SQLTools` | agno built-in | Execute SQL against DuckDB |
| `introspect_schema` | `tools/introspect.py` | Inspect table schemas at runtime |
| `save_validated_query` | `tools/save_query.py` | Save successful queries to knowledge |
| `save_learning` | `tools/save_learning.py` | Save learnings with post-insert verification |
| `export_to_excel` | `tools/export_excel.py` | Export query results to formatted .xlsx |
| `MCPTools` (Exa) | agno built-in | Web search for institutional knowledge |

### The Six Layers of Context

| Layer | Source | Code |
|-------|--------|------|
| 1. Table Usage | `dash/knowledge/tables/*.json` | `dash/context/semantic_model.py` |
| 2. Business Rules | `dash/knowledge/business/*.json` | `dash/context/business_rules.py` |
| 3. Query Patterns | `dash/knowledge/queries/*.sql` | Loaded into knowledge base |
| 4. Institutional Knowledge | Exa MCP | `dash/agents.py` |
| 5. Learnings | Learning Machine | `dash/tools/save_learning.py` |
| 6. Runtime Context | `introspect_schema` | `dash/tools/introspect.py` |

## Key Design Decisions

- **DuckDB for queries, PostgreSQL for state**: Agent queries TPC-H data in DuckDB. Knowledge, learnings, chat history, and embeddings live in PostgreSQL with pgvector.
- **Verified save_learning**: Agno's built-in `save_learning` silently swallows embedding failures. Our custom tool in `tools/save_learning.py` verifies persistence via search after insert, with one retry.
- **ALWAYS mode for learnings**: `LearnedKnowledgeConfig(mode=LearningMode.ALWAYS)` — auto-extracts learnings from every conversation. Uses Sonnet (cheaper) for extraction, Opus for main agent.
- **Tool factory pattern**: All custom tools use `create_*_tool(dependency)` factories that inject db connections or knowledge instances via closure.
- **Excel export**: `export_to_excel` generates production-grade `.xlsx` via xlsxwriter — styled headers, freeze panes, auto-filter, smart number format detection, alternating row stripes.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key (agent + learning extraction) |
| `OPENAI_API_KEY` | Yes | OpenAI embeddings (`text-embedding-3-small`) |
| `DUCKDB_PATH` | Yes | Absolute path to `data/tpch_sf1.db` |
| `EXA_API_KEY` | No | Exa web search MCP |
| `DB_*` | No | PostgreSQL config (defaults: `ai`/`ai`@`localhost:5432/ai`) |

## Known Issues

- Agno's `SQLTools.describe_table` uses `pg_catalog.pg_collation` which doesn't exist in DuckDB — harmless error in logs, agent uses `introspect_schema` as fallback
- `DUCKDB_PATH` defaults to `/app/data/tpch_sf1.db` (container path) — must be overridden for local dev
- Knowledge `load_knowledge.py` fails without `OPENAI_API_KEY` (embeddings return 0 dimensions)
