# Dash Evaluation Plan

## Overview

Dash is a self-learning data agent with 6 layers of context and continuous learning capabilities. This document outlines a comprehensive evaluation plan.

## Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│                    User Question                        │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│          Retrieve 6 Layers of Context                   │
│  1. Table Usage     → knowledge/tables/*.json           │
│  2. Human Annotations → knowledge/business/*.json       │
│  3. Query Patterns  → knowledge/queries/*.sql           │
│  4. Institutional   → Exa MCP (web search)              │
│  5. Learnings       → Learning Machine (auto)           │
│  6. Runtime Context → introspect_schema tool            │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│              Reason About Intent                        │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│           Generate Grounded SQL                         │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│         Execute & Interpret Results                     │
└─────────────┬───────────────┬───────────────────────────┘
              ↓               ↓
         ┌─────────┐    ┌─────────┐
         │ Success │    │  Error  │
         └────┬────┘    └────┬────┘
              ↓              ↓
              ↓         Diagnose → Fix → Save Learning
              ↓                          (never repeated)
              ↓
┌─────────────────────────────────────────────────────────┐
│         Return Insight (not just data)                  │
└────────────────────┬────────────────────────────────────┘
                     ↓
        Optionally save as Knowledge
```

## Two Knowledge Systems

| System | Purpose | Storage | Evolution |
|--------|---------|---------|-----------|
| **Knowledge** | Static, curated patterns | `dash_knowledge` vector DB | Curated by team + successful queries |
| **Learnings** | Dynamic discoveries | `dash_learnings` vector DB | Auto-discovered by Learning Machine |

## Evaluation Plan

### Phase 1: Environment Setup (30 min)

**Goal:** Get Dash running locally with sample F1 data

1. **Setup API Key**
   ```bash
   cp example.env .env
   # Edit .env and add OPENAI_API_KEY
   ```

2. **Start Docker Services**
   ```bash
   docker compose up -d --build
   ```
   - Verify containers: `dash-db` (PostgreSQL + pgvector) and `dash-api`
   - Check health: http://localhost:8000/docs

3. **Load Sample Data & Knowledge**
   ```bash
   docker exec -it dash-api python -m dash.scripts.load_data
   docker exec -it dash-api python -m dash.scripts.load_knowledge
   ```

4. **Connect to Agno UI**
   - Open: https://os.agno.com
   - Add OS → Local → http://localhost:8000
   - Connect

**Success Criteria:**
- [ ] API docs accessible at localhost:8000/docs
- [ ] Sample F1 data loaded (5 tables: drivers_championship, constructors_championship, race_wins, fastest_laps, race_results)
- [ ] Knowledge base loaded (table metadata, query patterns, business rules)
- [ ] Agno UI connected

---

### Phase 2: Basic Functionality Testing (45 min)

**Goal:** Validate core query capabilities on F1 dataset

**Test Queries:**

1. **Simple Aggregation**
   ```
   Who won the most races in 2019?
   ```
   - Expected: Hamilton with 11 wins
   - Observe: Context retrieval, SQL generation, insight delivery

2. **Championship Query**
   ```
   Which team won the 2020 constructors championship?
   ```
   - Expected: Mercedes
   - Watch for: Handling INTEGER position type

3. **Drivers Championship**
   ```
   Who won the 2020 drivers championship?
   ```
   - Expected: Hamilton
   - Watch for: Handling TEXT position type (position = '1')

4. **Historical Query**
   ```
   How many races has Lewis Hamilton won?
   ```
   - Expected: ~100+ race wins
   - Check: Insight quality (context, comparison, interpretation)

5. **Complex Comparison**
   ```
   Compare Ferrari vs Mercedes points 2015-2020
   ```
   - Expected: Year-by-year comparison with insights
   - Check: Multi-table query handling

**Success Criteria:**
- [ ] All queries return correct results
- [ ] Responses include insights, not just raw data
- [ ] Agent searches knowledge base before generating SQL
- [ ] SQL follows best practices (LIMIT 50, specific columns, ORDER BY)

**Observations to Document:**
- Response quality: Are insights meaningful?
- Context usage: Which layers are being retrieved?
- SQL quality: Correct handling of type differences?
- Error handling: Any failed queries?

---

### Phase 3: Learning System Evaluation (60 min)

**Goal:** Test continuous learning capabilities

#### 3A. Intentional Error Pattern

1. **Query with Type Mismatch**
   ```
   Who finished second in the 2019 drivers championship?
   ```
   - First run: May fail with type error (comparing '2' vs 2)
   - Expected: Agent introspects schema, fixes, saves learning
   - Verify: `save_learning` tool called with type gotcha

2. **Repeat Same Query**
   - Expected: Should succeed immediately using saved learning
   - Check: `search_learnings` returns previous fix

3. **Similar Query**
   ```
   Who finished third in the 2020 drivers championship?
   ```
   - Expected: Applies learned pattern automatically
   - No need to discover same type issue again

#### 3B. Date Parsing Challenges

1. **Query Requiring Date Parsing**
   ```
   How many races did Ferrari win in 2019?
   ```
   - Watch for: `TO_DATE(date, 'DD Mon YYYY')` usage
   - Expected: Agent knows date format from knowledge/learnings

2. **Verify Learning**
   - Check if date parsing pattern is saved
   - Test similar date-based query

#### 3C. Edge Case Handling

1. **Historical Boundary**
   ```
   Who won the constructors championship in 1950?
   ```
   - Expected: Agent knows constructors started in 1958
   - Should be in business rules or learnings

2. **Non-numeric Position Values**
   ```
   How many retirements were there in 2020?
   ```
   - Expected: Handles position = 'Ret' correctly

**Success Criteria:**
- [ ] Agent discovers and saves learnings from errors
- [ ] Learnings are retrieved in subsequent queries
- [ ] Pattern recognition across similar queries
- [ ] Learning Machine tools used appropriately

**Metrics to Track:**
- Number of learnings saved
- Learning retrieval rate
- Query success rate (first attempt vs subsequent)
- Time to fix (iterations needed)

---

### Phase 4: Evaluation Suite Analysis (45 min)

**Goal:** Run comprehensive eval suite and analyze results

#### 4A. String Matching Evals

```bash
docker exec -it dash-api python -m dash.evals.run_evals -v
```

- Tests: 16 test cases across 5 categories
  - basic (4 tests)
  - aggregation (5 tests)
  - data_quality (4 tests)
  - complex (3 tests)
  - edge_case (2 tests)

**Analyze:**
- Pass rate per category
- Common failure patterns
- Which types of queries work best?

#### 4B. LLM Grader Evals

```bash
docker exec -it dash-api python -m dash.evals.run_evals -g -v
```

- Uses GPT to evaluate response quality
- Checks for insights, not just correctness

**Analyze:**
- Quality scores per category
- Insight depth vs bare SQL results
- Contextual awareness

#### 4C. Golden SQL Comparison

```bash
docker exec -it dash-api python -m dash.evals.run_evals -r -v
```

- Executes golden SQL and compares results
- Validates correctness beyond string matching

**Analyze:**
- Exact match rate
- Result divergence patterns
- SQL approach differences

#### 4D. Full Evaluation

```bash
docker exec -it dash-api python -m dash.evals.run_evals -g -r -v
```

- All three modes combined
- Comprehensive quality assessment

**Success Criteria:**
- [ ] >90% pass rate on string matching
- [ ] >80% on LLM grader (quality)
- [ ] >85% on golden SQL comparison
- [ ] Documented failure patterns

---

### Phase 5: Architecture Deep Dive (60 min)

**Goal:** Understand implementation details

#### 5A. Knowledge System

1. **Inspect Knowledge Base**
   ```bash
   # Check what's in the knowledge base
   docker exec -it dash-db psql -U ai -d ai -c "SELECT COUNT(*) FROM dash_knowledge;"
   docker exec -it dash-db psql -U ai -d ai -c "SELECT name, content FROM dash_knowledge_contents LIMIT 5;"
   ```

2. **Review Knowledge Files**
   - Table metadata: `dash/knowledge/tables/`
   - Query patterns: `dash/knowledge/queries/`
   - Business rules: `dash/knowledge/business/`

3. **Analyze Context Structure**
   - Read: `dash/context/semantic_model.py`
   - Read: `dash/context/business_rules.py`

#### 5B. Learning Machine

1. **Inspect Learnings**
   ```bash
   docker exec -it dash-db psql -U ai -d ai -c "SELECT COUNT(*) FROM dash_learnings;"
   docker exec -it dash-db psql -U ai -d ai -c "SELECT name, content FROM dash_learnings_contents;"
   ```

2. **Trace Learning Flow**
   - Review: `dash/agents.py` (lines 175-180)
   - Understand: UserProfile, UserMemory, LearnedKnowledge configs

#### 5C. Tools & Capabilities

1. **Review Tool Implementations**
   - `dash/tools/introspect.py` - Runtime schema inspection
   - `dash/tools/save_query.py` - Validated query storage

2. **SQL Tools Usage**
   - Check how SQLTools connects to database
   - Review query execution flow

**Success Criteria:**
- [ ] Understand knowledge vs learnings separation
- [ ] Trace how context is retrieved and used
- [ ] Identify learning storage mechanism
- [ ] Map out tool integration points

---

### Phase 6: Comparison with OpenAI's Approach (30 min)

**Goal:** Analyze differences and similarities

**Read:**
- OpenAI blog: https://openai.com/index/inside-our-in-house-data-agent/
- Ashpreet's article: https://www.ashpreetbedi.com/articles/sql-agent

**Compare:**

| Aspect | OpenAI Agent | Dash | Notes |
|--------|--------------|------|-------|
| Context Layers | 6 layers | 6 layers | Same approach |
| Learning Method | Fine-tuning? | GPU-poor continuous learning | Different: Dash uses LearningMachine |
| Knowledge Storage | Vector DB | PgVector (hybrid search) | Similar |
| Query Validation | ? | Golden SQL + LLM grader | Well-tested |
| Insight Generation | Yes | Yes | Both focus on insights |
| Institutional Knowledge | Internal docs | Exa MCP (web search) | Different source |

**Key Differentiators:**
- Dash is open source
- Learning Machine = no GPU/fine-tuning needed
- Hybrid search (semantic + keyword)
- Built-in eval suite
- Agno platform integration

---

### Phase 7: Custom Data Testing (Optional, 90 min)

**Goal:** Evaluate on domain-specific data

**Steps:**

1. **Prepare Custom Dataset**
   - Load your own data into PostgreSQL
   - Create table metadata JSON files
   - Document business rules
   - Add validated query patterns

2. **Load Knowledge**
   ```bash
   docker exec -it dash-api python -m dash.scripts.load_knowledge
   ```

3. **Test Domain Queries**
   - Run 10-15 queries relevant to your domain
   - Monitor learning behavior
   - Document successes and failures

4. **Iterate on Knowledge**
   - Add more metadata based on failures
   - Document gotchas discovered
   - Build query pattern library

**Success Criteria:**
- [ ] Agent works on custom data
- [ ] Domain-specific learnings captured
- [ ] Knowledge base evolves appropriately

---

### Phase 8: Performance & Scalability (45 min)

**Goal:** Assess practical limits

#### 8A. Response Time

- Measure latency for different query types:
  - Simple queries (< 5s)
  - Complex queries (< 15s)
  - With/without knowledge retrieval

#### 8B. Knowledge Base Size

- Current: ~20 knowledge entries (F1 dataset)
- Test: Add 100+ entries
- Measure: Search performance degradation

#### 8C. Learning Accumulation

- Test: 50+ queries over 2 hours
- Monitor: Learnings growth rate
- Check: Retrieval accuracy as learnings grow

#### 8D. Concurrent Usage

- Simulate: Multiple users querying simultaneously
- Check: API responsiveness
- Monitor: Database connection pool

**Success Criteria:**
- [ ] Acceptable response times (< 30s for complex)
- [ ] Scales to 100+ knowledge entries
- [ ] Learning retrieval remains accurate
- [ ] Handles concurrent requests

---

## Evaluation Metrics Summary

### Quantitative Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Query Success Rate | >90% | Eval suite pass rate |
| Insight Quality | >80% | LLM grader scores |
| SQL Correctness | >85% | Golden SQL comparison |
| Learning Retention | >95% | Repeat query success |
| Avg Response Time | <15s | End-to-end latency |
| Context Retrieval Accuracy | >90% | Manual review |

### Qualitative Assessment

- [ ] Insight quality (beyond raw data)
- [ ] Learning effectiveness (no repeated mistakes)
- [ ] Knowledge organization (easy to extend)
- [ ] Error handling (graceful degradation)
- [ ] Developer experience (ease of setup/use)

---

## Key Files Reference

```
dash/
├── agents.py              # Main agent definition (Dash, Reasoning Dash)
├── knowledge/             # 6-layer context sources
│   ├── tables/           # Layer 1: Table metadata
│   ├── queries/          # Layer 3: Validated SQL patterns
│   └── business/         # Layer 2: Business rules
├── context/
│   ├── semantic_model.py # Semantic layer (table relationships)
│   └── business_rules.py # Business context string
├── tools/
│   ├── introspect.py     # Layer 6: Runtime schema inspection
│   └── save_query.py     # Save validated queries to knowledge
├── evals/
│   ├── test_cases.py     # 16 test cases (5 categories)
│   ├── grader.py         # LLM-based quality grader
│   └── run_evals.py      # Eval runner (3 modes)
└── scripts/
    ├── load_data.py      # Load F1 sample data
    └── load_knowledge.py # Load knowledge to vector DB
```

---

## Known Gotchas (from F1 Dataset)

| Issue | Solution | Learned From |
|-------|----------|--------------|
| `position` is TEXT in `drivers_championship` | Use `position = '1'` (string) | Table metadata |
| `position` is INTEGER in `constructors_championship` | Use `position = 1` (integer) | Table metadata |
| `date` is TEXT in `race_wins` | Use `TO_DATE(date, 'DD Mon YYYY')` | Query patterns |
| Constructors started 1958 | Don't query before 1958 | Business rules |
| `position` has non-numeric values | Handle 'Ret', 'DSQ', 'DNS', 'NC' | Data quality notes |

---

## Next Steps After Evaluation

1. **Document Findings**
   - Success rate by category
   - Learning effectiveness
   - Comparison with OpenAI approach
   - Identified gaps/limitations

2. **Test Improvements**
   - Add more query patterns
   - Enhance business rules
   - Test with larger knowledge bases

3. **Production Readiness**
   - Security review (no DROP/DELETE in SQL)
   - Rate limiting
   - Cost analysis (OpenAI API usage)
   - Monitoring and observability

4. **Custom Deployment**
   - Adapt to your data schema
   - Build domain-specific knowledge base
   - Train team on knowledge curation
   - Set up continuous learning workflow

---

## Resources

- **Repository:** https://github.com/agno-agi/dash
- **OpenAI Blog:** https://openai.com/index/inside-our-in-house-data-agent/
- **Deep Dive:** https://www.ashpreetbedi.com/articles/sql-agent
- **Agno Docs:** https://docs.agno.com
- **Discord:** https://agno.com/discord
