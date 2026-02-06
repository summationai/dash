# Dash Quick Start Evaluation

## 15-Minute Quick Start

### Setup (5 min)

```bash
# 1. Configure API key
cp example.env .env
echo "OPENAI_API_KEY=sk-your-key" >> .env

# 2. Start services
docker compose up -d --build

# 3. Wait for containers to be healthy
docker ps | grep dash

# 4. Load data and knowledge
docker exec -it dash-api python -m dash.scripts.load_data
docker exec -it dash-api python -m dash.scripts.load_knowledge
```

**Verify:** http://localhost:8000/docs should show API documentation

---

### Test (10 min)

#### Via Agno UI
1. Open: https://os.agno.com
2. Add OS → Local → `http://localhost:8000`
3. Click "Connect"

#### Try These Queries

```
1. Who won the most races in 2019?
   → Should return: Hamilton with 11 wins + insights

2. Compare Ferrari vs Mercedes points 2015-2020
   → Should return: Year-by-year comparison with context

3. Who finished second in 2019 drivers championship?
   → May trigger learning if type error occurs
   → Should fix and save learning

4. Who finished third in 2020 drivers championship?
   → Should use previous learning, succeed immediately
```

---

## One-Hour Evaluation Flow

```
┌─────────────────────────────────────────────────────────┐
│ Phase 1: Setup (15 min)                                 │
│ ✓ Start Docker containers                               │
│ ✓ Load F1 data (5 tables)                               │
│ ✓ Load knowledge base                                   │
│ ✓ Connect Agno UI                                       │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 2: Basic Queries (20 min)                         │
│ ✓ Test 5-6 sample queries                               │
│ ✓ Observe context retrieval                             │
│ ✓ Check insight quality                                 │
│ ✓ Review generated SQL                                  │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 3: Learning Test (15 min)                         │
│ ✓ Trigger intentional error (type mismatch)             │
│ ✓ Watch agent fix and save learning                     │
│ ✓ Repeat query → instant success                        │
│ ✓ Try similar query → learned pattern applied           │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 4: Run Evals (10 min)                             │
│ ✓ String matching: -v                                   │
│ ✓ LLM grader: -g -v                                     │
│ ✓ Golden SQL: -r -v                                     │
│ ✓ Review pass rates                                     │
└─────────────────────────────────────────────────────────┘
```

---

## Key Commands Cheatsheet

### Docker Operations
```bash
# Start
docker compose up -d --build

# Stop
docker compose down

# View logs
docker logs dash-api -f

# Shell access
docker exec -it dash-api bash
```

### Data & Knowledge
```bash
# Load F1 sample data
docker exec -it dash-api python -m dash.scripts.load_data

# Load knowledge (initial or update)
docker exec -it dash-api python -m dash.scripts.load_knowledge

# Recreate knowledge (fresh start)
docker exec -it dash-api python -m dash.scripts.load_knowledge --recreate
```

### Evaluations
```bash
# Basic eval (string matching)
docker exec -it dash-api python -m dash.evals.run_evals -v

# Specific category
docker exec -it dash-api python -m dash.evals.run_evals -c basic -v

# LLM grader
docker exec -it dash-api python -m dash.evals.run_evals -g -v

# Golden SQL comparison
docker exec -it dash-api python -m dash.evals.run_evals -r -v

# Full evaluation (all modes)
docker exec -it dash-api python -m dash.evals.run_evals -g -r -v
```

### CLI Mode
```bash
# Interactive CLI
docker exec -it dash-api python -m dash

# Test query
docker exec -it dash-api python -m dash.agents
```

### Database Inspection
```bash
# Access PostgreSQL
docker exec -it dash-db psql -U ai -d ai

# Check knowledge base size
docker exec -it dash-db psql -U ai -d ai -c "SELECT COUNT(*) FROM dash_knowledge;"

# Check learnings
docker exec -it dash-db psql -U ai -d ai -c "SELECT COUNT(*) FROM dash_learnings;"

# View knowledge entries
docker exec -it dash-db psql -U ai -d ai -c "SELECT name FROM dash_knowledge_contents;"

# View learnings
docker exec -it dash-db psql -U ai -d ai -c "SELECT name, content FROM dash_learnings_contents;"
```

---

## Expected Results

### Eval Suite Targets
- **String Matching:** >90% pass rate (14/16 tests)
- **LLM Grader:** >80% quality score
- **Golden SQL:** >85% exact match

### Test Cases Breakdown
```
basic (4 tests)         → Should: 100% (straightforward queries)
aggregation (5 tests)   → Should: 100% (GROUP BY, COUNT)
data_quality (4 tests)  → Should: 75-100% (type handling)
complex (3 tests)       → Should: 66-100% (JOINs, multi-table)
edge_case (2 tests)     → Should: 100% (boundary conditions)
```

---

## What to Look For

### ✅ Good Signs
- Agent searches knowledge base before writing SQL
- Insights provided, not just raw data
- Learnings saved after fixing errors
- Similar queries succeed using prior learnings
- SQL follows best practices (LIMIT, specific columns, ORDER BY)
- Handles type differences correctly (TEXT vs INTEGER)

### ⚠️  Red Flags
- Same error repeated multiple times
- No context retrieval before query generation
- Bare SQL results without interpretation
- SELECT * or missing LIMIT clauses
- Type errors not fixed
- No learning accumulation

---

## Quick Architecture Map

```
┌───────────────────────────────────────────────────────────┐
│                     USER QUESTION                         │
└──────────────────────────┬────────────────────────────────┘
                           ↓
┌───────────────────────────────────────────────────────────┐
│              6 LAYERS OF CONTEXT RETRIEVAL                │
├───────────────────────────────────────────────────────────┤
│ 1. Tables        → knowledge/tables/*.json (PgVector)     │
│ 2. Annotations   → knowledge/business/*.json (PgVector)   │
│ 3. Patterns      → knowledge/queries/*.sql (PgVector)     │
│ 4. Institutional → Exa MCP (web search)                   │
│ 5. Learnings     → Learning Machine (auto)                │
│ 6. Runtime       → introspect_schema tool                 │
└──────────────────────────┬────────────────────────────────┘
                           ↓
┌───────────────────────────────────────────────────────────┐
│                   GENERATE GROUNDED SQL                   │
│              (using retrieved context)                    │
└──────────────────────────┬────────────────────────────────┘
                           ↓
┌───────────────────────────────────────────────────────────┐
│                    EXECUTE & INTERPRET                    │
└─────┬────────────────────────────────────────────┬────────┘
      ↓                                            ↓
┌──────────┐                                  ┌──────────┐
│ SUCCESS  │                                  │  ERROR   │
└────┬─────┘                                  └────┬─────┘
     ↓                                             ↓
     ↓                                     ┌───────────────┐
     ↓                                     │ Diagnose      │
     ↓                                     │ Fix           │
     ↓                                     │ Save Learning │
     ↓                                     └───────┬───────┘
     ↓                                             ↓
     └─────────────────────────────────────────────┘
                           ↓
┌───────────────────────────────────────────────────────────┐
│              RETURN INSIGHT (not just data)               │
└──────────────────────────┬────────────────────────────────┘
                           ↓
              Optionally save_validated_query
```

---

## Two Knowledge Systems

```
┌─────────────────────────────────────────────────────────┐
│                     KNOWLEDGE                           │
│                 (Static, Curated)                       │
├─────────────────────────────────────────────────────────┤
│ • Table schemas and relationships                       │
│ • Validated SQL query patterns                          │
│ • Business rules and metrics                            │
│ • Data quality gotchas                                  │
│                                                         │
│ Storage: dash_knowledge (PgVector)                      │
│ Source: knowledge/ directory                            │
│ Updated: Manually curated + save_validated_query        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                     LEARNINGS                           │
│               (Dynamic, Discovered)                     │
├─────────────────────────────────────────────────────────┤
│ • Error patterns and fixes                              │
│ • Type gotchas (TEXT vs INTEGER)                        │
│ • Date format discoveries                               │
│ • Column quirks                                         │
│                                                         │
│ Storage: dash_learnings (PgVector)                      │
│ Source: Learning Machine (auto)                         │
│ Updated: Automatically on error → fix → save            │
└─────────────────────────────────────────────────────────┘
```

---

## F1 Dataset Schema

```
┌──────────────────────────────────────────────────────────┐
│              DRIVERS_CHAMPIONSHIP (1950-2020)           │
├──────────────────────────────────────────────────────────┤
│ year         : int                                       │
│ position     : TEXT ← ⚠️  Use position = '1' (string)   │
│ name         : text                                      │
│ driver_tag   : text                                      │
│ nationality  : text                                      │
│ team         : text                                      │
│ points       : float                                     │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│         CONSTRUCTORS_CHAMPIONSHIP (1958-2020)           │
├──────────────────────────────────────────────────────────┤
│ year         : int                                       │
│ position     : INTEGER ← ⚠️  Use position = 1 (int)     │
│ team         : text                                      │
│ points       : int                                       │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                   RACE_WINS (all time)                  │
├──────────────────────────────────────────────────────────┤
│ year         : int                                       │
│ race         : int                                       │
│ venue        : text                                      │
│ date         : TEXT ← ⚠️  Use TO_DATE(date, 'DD Mon YYYY')│
│ name         : text                                      │
│ name_tag     : text                                      │
│ team         : text                                      │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                 FASTEST_LAPS (all time)                 │
├──────────────────────────────────────────────────────────┤
│ year         : int                                       │
│ race         : int                                       │
│ venue        : text                                      │
│ name         : text                                      │
│ driver_tag   : text                                      │
│ nationality  : text                                      │
│ team         : text                                      │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                RACE_RESULTS (2017-2020)                 │
├──────────────────────────────────────────────────────────┤
│ year         : int                                       │
│ round        : int                                       │
│ venue        : text                                      │
│ position     : TEXT ← May be: '1', 'Ret', 'DSQ', 'DNS'  │
│ name         : text                                      │
│ team         : text                                      │
│ starting_grid: text                                      │
│ points       : float                                     │
└──────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Container won't start
```bash
# Check logs
docker logs dash-api
docker logs dash-db

# Rebuild from scratch
docker compose down -v
docker compose up -d --build
```

### Can't connect to database
```bash
# Wait for DB to be ready
docker exec -it dash-db pg_isready -U ai

# Check connection
docker exec -it dash-db psql -U ai -d ai -c "SELECT 1;"
```

### Knowledge not loading
```bash
# Check files exist
ls dash/knowledge/tables/
ls dash/knowledge/queries/
ls dash/knowledge/business/

# Recreate knowledge base
docker exec -it dash-api python -m dash.scripts.load_knowledge --recreate
```

### API not responding
```bash
# Check API health
curl http://localhost:8000/health

# Check FastAPI logs
docker logs dash-api -f --tail 100
```

---

## Success Checklist

After 1 hour of evaluation, you should be able to answer:

- [ ] Does Dash return correct SQL results?
- [ ] Are insights meaningful (not just raw data)?
- [ ] Does learning system work (errors → fixes → saved)?
- [ ] Do similar queries benefit from learnings?
- [ ] Does context retrieval happen before SQL generation?
- [ ] Are eval pass rates >85%?
- [ ] Can you add custom knowledge easily?

If YES to 6/7 → Dash is working as intended!
