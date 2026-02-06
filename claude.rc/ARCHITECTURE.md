# Dash Architecture Deep Dive

## System Overview

Dash is a **self-learning data agent** that combines 6 layers of context with continuous learning to deliver insights from SQL queries.

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER LAYER                              │
│   Agno UI (os.agno.com) ←→ REST API (localhost:8000)           │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT LAYER (Agno)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      Dash Agent                          │  │
│  │  Model: GPT-5.2 (OpenAI)                                 │  │
│  │  Instructions: SEMANTIC_MODEL + BUSINESS_CONTEXT         │  │
│  │  History: Last 5 runs                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE LAYER                              │
│  ┌────────────────────────┐   ┌──────────────────────────┐     │
│  │   dash_knowledge       │   │   dash_learnings         │     │
│  │   (Static/Curated)     │   │   (Dynamic/Discovered)   │     │
│  │                        │   │                          │     │
│  │ • Table schemas        │   │ • Error patterns         │     │
│  │ • Query patterns       │   │ • Type gotchas           │     │
│  │ • Business rules       │   │ • Column quirks          │     │
│  │                        │   │                          │     │
│  │ PgVector (hybrid)      │   │ PgVector (hybrid)        │     │
│  │ text-embedding-3-small │   │ text-embedding-3-small   │     │
│  └────────────────────────┘   └──────────────────────────┘     │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                       TOOLS LAYER                               │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   SQLTools     │  │  introspect  │  │  save_validated  │   │
│  │                │  │  _schema     │  │  _query          │   │
│  │  Execute SQL   │  │              │  │                  │   │
│  │  Read/Write    │  │  Runtime DB  │  │  Store to        │   │
│  │                │  │  inspection  │  │  knowledge       │   │
│  └────────────────┘  └──────────────┘  └──────────────────┘   │
│                                                                 │
│  ┌────────────────┐  ┌──────────────────────────────────────┐ │
│  │   MCPTools     │  │      Learning Machine Tools          │ │
│  │                │  │                                      │ │
│  │  Exa Web       │  │  • search_learnings                  │ │
│  │  Search        │  │  • save_learning                     │ │
│  │                │  │  • user_profile                      │ │
│  └────────────────┘  │  • user_memory                       │ │
│                      └──────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              PostgreSQL + PgVector                        │ │
│  │                                                           │ │
│  │  • F1 dataset tables (drivers, constructors, races)      │ │
│  │  • dash_knowledge (vector table)                         │ │
│  │  • dash_knowledge_contents (metadata)                    │ │
│  │  • dash_learnings (vector table)                         │ │
│  │  • dash_learnings_contents (metadata)                    │ │
│  │  • agno system tables (runs, sessions, messages)         │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Six Layers of Context

### Layer 1: Table Usage (Semantic Model)

**Source:** `dash/context/semantic_model.py` + `dash/knowledge/tables/*.json`

**Purpose:** Provides table schemas, column types, and relationships

**Example:**
```json
{
  "table_name": "drivers_championship",
  "table_columns": [
    {
      "name": "position",
      "type": "text",
      "description": "Use position = '1' (string) to get champion"
    }
  ],
  "data_quality_notes": [
    "position is TEXT type - must compare with strings",
    "Differs from constructors_championship (INTEGER)"
  ]
}
```

**How It Works:**
1. Tables metadata loaded into PgVector via `load_knowledge.py`
2. Agent searches knowledge base with hybrid search (semantic + keyword)
3. Retrieved schemas inform SQL generation

---

### Layer 2: Human Annotations (Business Context)

**Source:** `dash/context/business_rules.py` + `dash/knowledge/business/*.json`

**Purpose:** Business definitions, metrics, common gotchas

**Example:**
```json
{
  "metrics": [
    {
      "name": "Championship Wins",
      "definition": "Count of position = '1' in drivers_championship"
    }
  ],
  "common_gotchas": [
    {
      "issue": "Constructors Championship didn't exist before 1958",
      "solution": "Filter year >= 1958 for constructor queries"
    }
  ]
}
```

**How It Works:**
- Loaded into same knowledge base as tables
- Retrieved during query planning
- Prevents common business logic errors

---

### Layer 3: Query Patterns (Validated SQL)

**Source:** `dash/knowledge/queries/*.sql`

**Purpose:** Known-good SQL patterns for common queries

**Example:**
```sql
-- <query name>driver_championships_all_time</query name>
-- <query description>
-- Which driver won the most World Championships?
-- Handles: position as TEXT in drivers_championship
-- </query description>
-- <query>
SELECT
    name AS driver,
    COUNT(*) AS championship_wins
FROM drivers_championship
WHERE position = '1'  -- TEXT comparison (note the quotes!)
GROUP BY name
ORDER BY championship_wins DESC
LIMIT 10
-- </query>
```

**How It Works:**
- Structured with XML-like tags for parsing
- Embedded in knowledge base with description
- Agent retrieves similar patterns for new queries
- Can be extended via `save_validated_query` tool

---

### Layer 4: Institutional Knowledge (External Context)

**Source:** Exa MCP (web search)

**Purpose:** Access external documentation, research, domain knowledge

**How It Works:**
```python
MCPTools(url=f"https://mcp.exa.ai/mcp?exaApiKey={EXA_API_KEY}&tools=web_search_exa")
```

- Optional (requires EXA_API_KEY)
- Provides web_search_exa tool to agent
- Searches web for additional context
- Example: "What changed in F1 rules in 2020?"

---

### Layer 5: Learnings (Continuous Learning)

**Source:** Learning Machine (Agno framework)

**Purpose:** Auto-discovered patterns, errors, fixes

**Configuration:**
```python
learning=LearningMachine(
    knowledge=dash_learnings,
    user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
    user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
    learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
)
```

**Provides Tools:**
- `search_learnings(query)` - Retrieve past learnings
- `save_learning(title, learning)` - Store discovered patterns
- `user_profile` - Structured facts about user/domain
- `user_memory` - Unstructured observations

**Learning Flow:**
```
Query → Error (type mismatch)
  ↓
Agent diagnoses: "position should be '1' not 1"
  ↓
save_learning(
  title="drivers_championship position is TEXT",
  learning="Use position = '1' (string) not 1 (integer)"
)
  ↓
Next similar query: search_learnings retrieves fix
  ↓
Apply immediately, no error
```

---

### Layer 6: Runtime Context (Live Schema)

**Source:** `dash/tools/introspect.py`

**Purpose:** Real-time database schema inspection

**Tool:**
```python
introspect_schema = create_introspect_schema_tool(db_url)
```

**When Used:**
- Schema changes not in static knowledge
- Error debugging (verify actual column types)
- Handling unknown tables

**Example:**
```python
# Agent encounters error
agent: introspect_schema(table='drivers_championship', column='position')
# Returns: {"type": "text", "nullable": true}
# Agent: "Ah, it's TEXT not INTEGER, let me fix..."
```

---

## GPU-Poor Continuous Learning

**Key Insight:** Learning without fine-tuning or retraining

### Traditional Approach (GPU-Rich)
```
Error → Collect examples → Fine-tune model → Deploy
Time: Days/weeks
Cost: GPU hours + engineering
Risk: Model drift, catastrophic forgetting
```

### Dash Approach (GPU-Poor)
```
Error → Diagnose → Fix → save_learning → Done
Time: Seconds
Cost: Vector DB storage (minimal)
Risk: Minimal (append-only learning)
```

### Implementation (5 lines of code!)
```python
learning=LearningMachine(
    knowledge=data_agent_learnings,
    user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
    user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
    learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
)
```

### How It Works

1. **User Profile** (Structured Facts)
   - User role, domain, preferences
   - Business rules specific to user
   - Stored as structured JSON

2. **User Memory** (Unstructured Observations)
   - "User prefers revenue in dollars not cents"
   - "User's team focuses on 2019-2020 data"
   - Stored as text snippets

3. **Learned Knowledge** (Discovered Patterns)
   - Error patterns → solutions
   - Type gotchas
   - Column quirks

All three stored in `dash_learnings` vector DB, retrieved via hybrid search.

---

## Hybrid Search (PgVector)

### Configuration
```python
PgVector(
    db_url=db_url,
    table_name="dash_knowledge",
    search_type=SearchType.hybrid,  # ← Semantic + Keyword
    embedder=OpenAIEmbedder(id="text-embedding-3-small"),
)
```

### How Hybrid Search Works

**Semantic Search:**
- Query: "Who won the most races?"
- Embedding: [0.23, -0.45, 0.67, ...]
- Matches: Similar meaning (wins, victories, championships)

**Keyword Search:**
- Query: "position = '1'"
- Tokens: ["position", "=", "'1'"]
- Matches: Exact SQL patterns with position

**Hybrid = Best of Both:**
- Ranks results by combined score
- Catches exact matches (keywords) + similar concepts (semantic)

---

## Agent Workflow

### Complete Query Flow

```
┌──────────────────────────────────────────────────────────┐
│ 1. Receive Question                                      │
│    "Who won the most races in 2019?"                     │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 2. Search Knowledge & Learnings (Parallel)               │
│    search_knowledge_base("races wins 2019")              │
│    search_learnings("races wins")                        │
│                                                           │
│    Retrieved:                                            │
│    • race_wins table schema                              │
│    • common_queries.sql (similar patterns)               │
│    • date parsing gotcha: TO_DATE(date, 'DD Mon YYYY')   │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 3. Reason About Intent                                   │
│    • Need: COUNT wins by driver                          │
│    • Filter: year 2019                                   │
│    • Return: Top driver with context                     │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 4. Generate SQL (Grounded in Context)                    │
│    SELECT name, COUNT(*) as wins                         │
│    FROM race_wins                                        │
│    WHERE TO_DATE(date, 'DD Mon YYYY') >= '2019-01-01'    │
│      AND TO_DATE(date, 'DD Mon YYYY') < '2020-01-01'     │
│    GROUP BY name                                         │
│    ORDER BY wins DESC                                    │
│    LIMIT 1                                               │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 5. Execute SQL                                           │
│    Result: [('Lewis Hamilton', 11)]                      │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 6. Interpret & Add Insights                              │
│    • Hamilton won 11 races                               │
│    • There were 21 races in 2019 (52% win rate)          │
│    • 7 more wins than Bottas (second place)              │
│    • Secured his 6th world championship                  │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 7. Offer to Save Query (Optional)                        │
│    "Would you like me to save this query for future     │
│     reference?"                                          │
│    → save_validated_query(...)                           │
└──────────────────────────────────────────────────────────┘
```

### Error Recovery Flow

```
┌──────────────────────────────────────────────────────────┐
│ Query Execution Error                                    │
│ "column drivers_championship.position is of type text    │
│  but expression is of type integer"                      │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ Diagnose                                                 │
│ introspect_schema(table='drivers_championship',          │
│                   column='position')                     │
│ → Returns: {"type": "text"}                              │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ Fix SQL                                                  │
│ Change: WHERE position = 1                               │
│ To:     WHERE position = '1'                             │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ Execute Fixed SQL                                        │
│ → Success!                                               │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ Save Learning                                            │
│ save_learning(                                           │
│   title="drivers_championship position is TEXT",        │
│   learning="position column is TEXT type. Always use    │
│             position = '1' (string) not 1 (integer).    │
│             This differs from constructors_championship  │
│             where position is INTEGER."                  │
│ )                                                        │
└──────────────────────────────────────────────────────────┘
```

---

## Comparison: OpenAI vs Dash

| Aspect | OpenAI Data Agent | Dash | Winner |
|--------|-------------------|------|--------|
| **Context Layers** | 6 layers | 6 layers | Tie |
| **Learning Method** | Unclear (likely fine-tuning) | GPU-poor continuous learning | Dash (simpler) |
| **Open Source** | No | Yes | Dash |
| **Vector DB** | Proprietary | PgVector (open) | Dash |
| **Search Type** | Likely semantic | Hybrid (semantic + keyword) | Dash |
| **Evaluation Suite** | Unknown | 16 tests, 3 modes | Dash |
| **Institutional Knowledge** | Internal docs | Exa MCP (web) | Tie |
| **Deployment** | Internal only | Docker, Railway, local | Dash |
| **UI** | Internal | Agno (open platform) | Dash |
| **Cost** | Unknown | OpenAI API + hosting | TBD |
| **Learning Storage** | Unknown | PgVector (append-only) | Dash (transparent) |
| **Production Ready** | Yes (internal) | Maybe (new project) | OpenAI |

### Key Differentiators

**OpenAI Advantages:**
- Battle-tested in production
- Likely optimized for scale
- Internal tooling integration

**Dash Advantages:**
- Open source (inspect, modify, extend)
- No GPU/fine-tuning required
- Easy local development
- Clear separation: knowledge vs learnings
- Comprehensive eval suite
- Docker-based deployment

---

## Technical Architecture Details

### Database Schema

```sql
-- Knowledge Base
CREATE TABLE dash_knowledge (
  id TEXT PRIMARY KEY,
  name TEXT,
  meta_ JSONB,
  embedding VECTOR(1536),  -- text-embedding-3-small
  usage JSONB,
  -- PgVector indexes for hybrid search
  ...
);

CREATE TABLE dash_knowledge_contents (
  id TEXT PRIMARY KEY,
  name TEXT,
  content TEXT,
  ...
);

-- Learnings (same structure, separate table)
CREATE TABLE dash_learnings (...);
CREATE TABLE dash_learnings_contents (...);

-- F1 Dataset
CREATE TABLE drivers_championship (
  index INTEGER,
  year INTEGER,
  position TEXT,  -- ⚠️  TEXT not INTEGER
  name TEXT,
  ...
);

CREATE TABLE constructors_championship (
  year INTEGER,
  position INTEGER,  -- ⚠️  INTEGER not TEXT
  team TEXT,
  ...
);

-- More F1 tables...
```

### API Endpoints

```
GET  /                  → Root (redirect to docs)
GET  /docs              → FastAPI auto-generated docs
POST /v1/agent/run      → Run agent (Agno protocol)
GET  /v1/agent/runs     → List runs
GET  /v1/agent/sessions → List sessions
...
```

### Agent Configuration

```yaml
# app/config.yaml
agents:
  - name: dash
    model: gpt-5.2
    description: Self-learning data agent
    instructions: [loaded from dash.agents]
    tools: [SQLTools, introspect_schema, save_validated_query, MCPTools]
    knowledge: dash_knowledge
    learning: dash_learnings
```

---

## Extending Dash

### Add Custom Data

1. **Load Your Data**
   ```python
   # In your script
   import psycopg2
   conn = psycopg2.connect(db_url)
   # Load your tables
   ```

2. **Create Table Metadata**
   ```json
   // dash/knowledge/tables/orders.json
   {
     "table_name": "orders",
     "table_description": "Customer orders",
     "data_quality_notes": [
       "created_at is UTC",
       "amount stored in cents"
     ],
     "table_columns": [...]
   }
   ```

3. **Add Query Patterns**
   ```sql
   -- dash/knowledge/queries/revenue.sql
   -- <query name>monthly_revenue</query name>
   -- <query description>...</query description>
   -- <query>
   SELECT ...
   -- </query>
   ```

4. **Load Knowledge**
   ```bash
   docker exec -it dash-api python -m dash.scripts.load_knowledge
   ```

### Add Business Rules

```json
// dash/knowledge/business/metrics.json
{
  "metrics": [
    {
      "name": "MRR",
      "definition": "Monthly recurring revenue from active subscriptions"
    }
  ],
  "common_gotchas": [
    {
      "issue": "Trial subscriptions",
      "solution": "Exclude status = 'trial' from MRR calculations"
    }
  ]
}
```

---

## Cost Analysis

### OpenAI API Usage (per query)

| Component | Tokens | Cost (GPT-5.2) |
|-----------|--------|----------------|
| Knowledge retrieval | ~2,000 | $0.01 |
| SQL generation | ~1,500 | $0.008 |
| Insight generation | ~1,000 | $0.005 |
| Learning (if error) | +500 | +$0.003 |
| **Total per query** | ~5,000 | **~$0.026** |

### Embedding Costs

| Component | Vectors | Cost |
|-----------|---------|------|
| Initial knowledge load | ~50 | $0.0001 |
| Per learning saved | 1 | $0.000002 |

### Infrastructure

| Component | Cost (monthly) |
|-----------|----------------|
| PostgreSQL + PgVector | $10-50 (Railway/AWS RDS) |
| Container hosting | $5-20 (Railway/Render) |

**Total:** ~$50-100/month + $0.026/query

---

## Key Files Reference

```
dash/
├── agents.py                    # Main agent definition
│   └── dash: Agent              # Primary agent (lines 166-188)
│   └── reasoning_dash: Agent    # With reasoning tools (191-196)
│
├── knowledge/                   # Static knowledge (Layer 1-3)
│   ├── tables/                  # Layer 1: Table metadata
│   │   ├── drivers_championship.json
│   │   ├── constructors_championship.json
│   │   └── ...
│   ├── queries/                 # Layer 3: Query patterns
│   │   └── common_queries.sql
│   └── business/                # Layer 2: Business rules
│       └── metrics.json
│
├── context/                     # Context builders
│   ├── semantic_model.py        # Table relationship string
│   └── business_rules.py        # Business context string
│
├── tools/                       # Agent tools
│   ├── introspect.py            # Layer 6: Runtime schema
│   └── save_query.py            # Save validated queries
│
├── evals/                       # Evaluation system
│   ├── test_cases.py            # 16 test cases
│   ├── grader.py                # LLM-based grader
│   └── run_evals.py             # Eval runner
│
└── scripts/                     # Utility scripts
    ├── load_data.py             # Load F1 dataset
    └── load_knowledge.py        # Load knowledge to PgVector
```

---

## Performance Characteristics

### Query Latency (F1 dataset)

| Query Type | Latency | Breakdown |
|------------|---------|-----------|
| Simple (cached knowledge) | 3-5s | LLM: 2s, DB: 1s, Overhead: 1s |
| Complex (JOIN, multi-table) | 8-12s | LLM: 4s, DB: 3s, Overhead: 2s |
| With error recovery | 10-15s | +5s for introspect + retry |

### Knowledge Base Size

| Metric | F1 Dataset | Expected at Scale |
|--------|------------|-------------------|
| Tables | 5 | 50-100 |
| Query patterns | 10 | 100-500 |
| Business rules | 5 | 20-50 |
| Learnings (after 100 queries) | 10-20 | 100-500 |
| Total vector entries | ~40 | 300-1200 |

### Search Performance

- Hybrid search: ~50-200ms for top 10 results
- Scales well to 10,000+ vectors (PgVector optimized)
- May need index tuning at 100,000+ vectors

---

## Security Considerations

### SQL Injection Protection

**Built-in:**
- Agent uses SQLAlchemy/psycopg2 (parameterized queries)
- No direct string concatenation

**Limitations:**
- Agent can still generate `DROP`, `DELETE`, `UPDATE`
- Need to configure DB user with read-only permissions

### Recommended Setup

```sql
-- Create read-only user
CREATE USER dash_readonly PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE ai TO dash_readonly;
GRANT USAGE ON SCHEMA public TO dash_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dash_readonly;
-- No INSERT, UPDATE, DELETE, DROP
```

### API Security

- No authentication in current implementation
- Deploy behind API gateway with auth
- Rate limiting recommended

---

## Future Enhancements

### Potential Improvements

1. **Multi-tenant Support**
   - Separate knowledge bases per tenant
   - User-specific learnings

2. **Query Optimization**
   - Explain plan analysis
   - Suggest indexes

3. **Data Profiling**
   - Auto-generate table metadata
   - Detect data quality issues

4. **Collaborative Learning**
   - Share learnings across team
   - Voting on query patterns

5. **Advanced Reasoning**
   - Multi-step analysis
   - What-if scenarios

6. **Real-time Data**
   - Streaming query results
   - Live dashboard integration

---

## References

- **Dash Repository:** https://github.com/agno-agi/dash
- **OpenAI Blog:** https://openai.com/index/inside-our-in-house-data-agent/
- **SQL Agent Deep Dive:** https://www.ashpreetbedi.com/articles/sql-agent
- **Agno Framework:** https://github.com/agno-agi/agno
- **PgVector:** https://github.com/pgvector/pgvector
