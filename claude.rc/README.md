# Dash Evaluation Documentation

Welcome to the Dash evaluation documentation! This directory contains comprehensive guides for evaluating Dash, a self-learning data agent.

## What is Dash?

Dash is an **open-source data agent** that:
- Uses **6 layers of context** to ground SQL generation
- Implements **gpu-poor continuous learning** (learns without fine-tuning)
- Delivers **insights, not just data**
- **Never repeats mistakes** (auto-saves learnings)

Inspired by [OpenAI's internal data agent](https://openai.com/index/inside-our-in-house-data-agent/).

---

## Documentation Overview

```
claude.rc/
├── README.md              ← You are here
├── QUICK_START.md         ← 15-minute quickstart + 1-hour eval
├── EVALUATION_PLAN.md     ← Comprehensive 8-phase evaluation plan
└── ARCHITECTURE.md        ← Deep dive: architecture, tech stack, comparison
```

### 📋 Start Here: QUICK_START.md

**Best for:** Quick hands-on evaluation (1 hour)

**Contents:**
- 15-minute setup guide
- Sample test queries
- Commands cheatsheet
- Expected results
- Troubleshooting
- Success checklist

**When to use:** You want to get Dash running and test basic functionality ASAP.

---

### 📊 Comprehensive: EVALUATION_PLAN.md

**Best for:** Thorough evaluation (4-6 hours)

**Contents:**
- 8-phase evaluation plan
  1. Environment Setup (30 min)
  2. Basic Functionality Testing (45 min)
  3. Learning System Evaluation (60 min)
  4. Evaluation Suite Analysis (45 min)
  5. Architecture Deep Dive (60 min)
  6. Comparison with OpenAI (30 min)
  7. Custom Data Testing (90 min, optional)
  8. Performance & Scalability (45 min)
- Metrics and success criteria
- Observation guidelines
- Key files reference

**When to use:** You want a complete, structured evaluation covering all aspects.

---

### 🏗️ Technical: ARCHITECTURE.md

**Best for:** Understanding how Dash works internally

**Contents:**
- System architecture diagrams
- 6 layers of context (detailed)
- GPU-poor continuous learning explained
- Hybrid search (PgVector)
- Complete agent workflow
- OpenAI vs Dash comparison
- Cost analysis
- Security considerations
- Extension guide

**When to use:** You want to understand implementation details, make architectural decisions, or extend Dash.

---

## Quick Reference

### The 6 Layers of Context

```
1. Table Usage        → knowledge/tables/*.json (PgVector)
2. Human Annotations  → knowledge/business/*.json (PgVector)
3. Query Patterns     → knowledge/queries/*.sql (PgVector)
4. Institutional      → Exa MCP (web search)
5. Learnings          → Learning Machine (auto-discovered)
6. Runtime Context    → introspect_schema tool
```

### Two Knowledge Systems

| System | Purpose | Updated |
|--------|---------|---------|
| **Knowledge** | Static patterns (curated) | Manually + save_validated_query |
| **Learnings** | Dynamic discoveries | Automatically on error→fix |

### Quick Start Commands

```bash
# Setup
cp example.env .env  # Add OPENAI_API_KEY
docker compose up -d --build
docker exec -it dash-api python -m dash.scripts.load_data
docker exec -it dash-api python -m dash.scripts.load_knowledge

# Test
# Open: https://os.agno.com → Add Local → http://localhost:8000

# Evaluate
docker exec -it dash-api python -m dash.evals.run_evals -v      # String matching
docker exec -it dash-api python -m dash.evals.run_evals -g -v   # LLM grader
docker exec -it dash-api python -m dash.evals.run_evals -r -v   # Golden SQL
docker exec -it dash-api python -m dash.evals.run_evals -g -r -v # All modes
```

---

## Recommended Evaluation Path

### For First-Time Users (1 hour)

```
1. QUICK_START.md → Setup (15 min)
   ↓
2. QUICK_START.md → Test queries (20 min)
   ↓
3. QUICK_START.md → Run evals (10 min)
   ↓
4. ARCHITECTURE.md → Skim overview (15 min)
```

### For Thorough Evaluation (1 day)

```
1. QUICK_START.md → Setup + basic tests (30 min)
   ↓
2. EVALUATION_PLAN.md → Follow Phase 1-4 (3 hours)
   ↓
3. ARCHITECTURE.md → Deep dive (1 hour)
   ↓
4. EVALUATION_PLAN.md → Phase 5-8 (3 hours)
   ↓
5. Document findings, compare with OpenAI approach
```

### For Technical Architecture Review (2 hours)

```
1. ARCHITECTURE.md → System overview (20 min)
   ↓
2. ARCHITECTURE.md → 6 layers + learning system (40 min)
   ↓
3. Review code: dash/agents.py, dash/tools/, dash/evals/
   ↓
4. ARCHITECTURE.md → Comparison, cost, security (30 min)
   ↓
5. EVALUATION_PLAN.md → Phase 8 (performance) (30 min)
```

---

## Key Evaluation Questions

After your evaluation, you should be able to answer:

### Functionality ✅
- [ ] Does Dash generate correct SQL?
- [ ] Are insights meaningful (beyond raw data)?
- [ ] Does context retrieval work (6 layers)?
- [ ] Does the agent follow SQL best practices?

### Learning System 🧠
- [ ] Do errors trigger learning saves?
- [ ] Are learnings retrieved in subsequent queries?
- [ ] Does the agent avoid repeating mistakes?
- [ ] Does learning accumulate over time?

### Quality 📊
- [ ] Eval pass rates >85%?
- [ ] Response quality scores >80%?
- [ ] SQL correctness >90%?
- [ ] Handling of edge cases?

### Architecture 🏗️
- [ ] Understand knowledge vs learnings separation?
- [ ] How does hybrid search work?
- [ ] What are the performance characteristics?
- [ ] How does it compare to OpenAI's approach?

### Production Readiness 🚀
- [ ] Security concerns addressed?
- [ ] Scalability validated?
- [ ] Cost implications understood?
- [ ] Extension path clear?

---

## Visual Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Question                        │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│     Retrieve 6 Layers of Context (Hybrid Search)        │
│  1. Tables    2. Annotations    3. Patterns             │
│  4. External  5. Learnings      6. Runtime              │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│           Generate Grounded SQL + Execute               │
└─────────────┬───────────────┬───────────────────────────┘
              ↓               ↓
         ┌─────────┐    ┌─────────┐
         │ Success │    │  Error  │
         └────┬────┘    └────┬────┘
              ↓              ↓
              ↓         Fix → Save Learning
              ↓
              ↓
┌─────────────────────────────────────────────────────────┐
│         Return Insight (not just data)                  │
└─────────────────────────────────────────────────────────┘
```

---

## F1 Dataset Overview

The sample dataset contains Formula 1 racing data from 1950-2020:

**Tables:**
- `drivers_championship` - Driver standings (position is TEXT ⚠️)
- `constructors_championship` - Constructor standings (position is INTEGER ⚠️)
- `race_wins` - Individual race wins (date is TEXT, needs TO_DATE ⚠️)
- `fastest_laps` - Fastest lap records
- `race_results` - Detailed race results (position may be 'Ret', 'DSQ', etc. ⚠️)

**Known Gotchas:** (These test the learning system!)
- Type inconsistency: `position` is TEXT vs INTEGER in different tables
- Date parsing: `date` stored as text, requires `TO_DATE(date, 'DD Mon YYYY')`
- Non-numeric positions: 'Ret', 'DSQ', 'DNS', 'NC'
- Historical boundary: Constructors championship started 1958

---

## Sample Test Queries

### Basic Queries
```
Who won the most races in 2019?
→ Expected: Hamilton (11 wins)

Which team won the 2020 constructors championship?
→ Expected: Mercedes

How many races has Lewis Hamilton won?
→ Expected: ~100+ with historical context
```

### Learning Tests
```
Who finished second in the 2019 drivers championship?
→ May fail initially (type error), should learn and fix

Who finished third in the 2020 drivers championship?
→ Should succeed immediately using learned pattern
```

### Complex Queries
```
Compare Ferrari vs Mercedes points 2015-2020
→ Year-by-year comparison with insights

Which driver won the most races for Ferrari?
→ Historical analysis with context
```

---

## Success Metrics

| Metric | Target | Good | Excellent |
|--------|--------|------|-----------|
| Query Success Rate | >85% | >90% | >95% |
| Insight Quality (LLM) | >75% | >80% | >90% |
| SQL Correctness | >80% | >85% | >95% |
| Learning Retention | >90% | >95% | 100% |
| Avg Response Time | <20s | <15s | <10s |

---

## Tech Stack Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent Framework | Agno | Agent orchestration, tools, knowledge |
| LLM | OpenAI GPT-5.2 | Query understanding, SQL generation |
| Vector DB | PgVector | Hybrid search (semantic + keyword) |
| Embeddings | text-embedding-3-small | Context vectorization |
| Database | PostgreSQL 18 | Data + vector storage |
| API | FastAPI | REST endpoints |
| UI | Agno OS | Web interface |
| Deployment | Docker Compose | Local/production deployment |

---

## Key Differentiators vs OpenAI

| Feature | OpenAI | Dash |
|---------|--------|------|
| Open Source | ❌ | ✅ |
| Learning Method | Unknown | GPU-poor (no fine-tuning) |
| Evaluation Suite | ❌ | ✅ (16 tests, 3 modes) |
| Local Development | ❌ | ✅ |
| Cost Transparency | ❌ | ✅ |
| Extensibility | ❌ | ✅ |

---

## Next Steps

1. **Quick Eval:** Start with `QUICK_START.md` (1 hour)
2. **Deep Dive:** Follow `EVALUATION_PLAN.md` (1 day)
3. **Architecture:** Read `ARCHITECTURE.md` (2 hours)
4. **Custom Data:** Test with your own dataset
5. **Production:** Deploy and integrate

---

## Resources

- **Repository:** https://github.com/agno-agi/dash
- **OpenAI Blog:** https://openai.com/index/inside-our-in-house-data-agent/
- **SQL Agent Article:** https://www.ashpreetbedi.com/articles/sql-agent
- **Agno Docs:** https://docs.agno.com
- **Discord:** https://agno.com/discord

---

## Support

- **Issues:** https://github.com/agno-agi/dash/issues
- **Discussions:** https://github.com/agno-agi/dash/discussions
- **Discord:** https://agno.com/discord

---

## Contributing

Found an issue or want to improve Dash?
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

**Happy Evaluating! 🚀**

*Created: 2026-02-03*
*Dash Version: Latest (main branch)*
