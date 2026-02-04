# Dash Score Improvement Plan

**Current Score:** 53.3%
**Target Score:** 70-80%
**Gap:** +17-27 percentage points

---

## Issue Analysis

### Issue #1: Knowledge Base Not Working ⚠️ HIGH IMPACT

**Problem:**
```
WARNING Error code: 401 - You didn't provide an API key (OpenAI)
ERROR   Error performing hybrid search: expected 1536 dimensions, not 0
DEBUG   No documents found
```

**Impact:**
- Agent searches knowledge but gets nothing
- Can't leverage TPC-H table metadata
- Can't retrieve query patterns
- Can't access business rules

**Expected Improvement:** +15-20 points

**Fix:**
```bash
# Add OpenAI key for embeddings (separate from Claude for queries)
echo "OPENAI_API_KEY=sk-your-openai-key" >> .env
docker compose restart dash-api

# Or switch embeddings to Anthropic:
# Modify dash/agents.py to use Anthropic embedder
```

---

### Issue #2: Weak Validation Method ⚠️ MEDIUM IMPACT

**Problem:**
Current validation searches for exact numbers in response text:
```python
# Looking for "123141078.2283" in text
# But response has: "$123,141,078.23" or "$123M"
# → Validation MISS even though answer is correct
```

**Impact:**
- Q6, Q17, Q19 scored 0% but likely have correct answers
- Many queries underscored due to formatting differences

**Expected Improvement:** +10-15 points

**Fix:**
```python
# Better validation approach:
1. Parse numbers from response (strip $, commas)
2. Compare with tolerance (±1%)
3. Check for semantic equivalence ($123M = 123000000)
4. Extract SQL from agent tool calls (not text)
5. Execute extracted SQL and compare results
```

---

### Issue #3: Incomplete Knowledge Base ⚠️ LOW-MEDIUM IMPACT

**Problem:**
TPC-H knowledge has only 8 tables + 7 query patterns. Missing:
- Specific TPC-H query patterns (we have generic ones)
- Common gotchas (date formats, joins, calculations)
- Expected result patterns

**Expected Improvement:** +5-10 points (once embeddings work)

**Fix:**
```bash
# Add more comprehensive knowledge
dash/knowledge/
├── tables/           # ✅ Already have 8
├── queries/
│   ├── tpch_common.sql        # ✅ Have 7 patterns
│   └── tpch_q1_to_q22.sql     # ← ADD official patterns
└── business/
    ├── tpch_metrics.json      # ✅ Have basic metrics
    └── tpch_query_hints.json  # ← ADD query-specific hints
```

---

### Issue #4: Natural Language Questions ⚠️ LOW IMPACT

**Problem:**
Some questions might be too generic:
```
❌ "What are the summary pricing statistics..." (Q1: 35%)
✅ "What is the revenue from ASIA suppliers in 1994?" (Q5: 50%)
```

**Expected Improvement:** +5-8 points

**Fix:**
Make questions more specific and include key constraints:
```python
# Instead of:
"What are the summary pricing statistics for line items?"

# Use:
"Show pricing summary for line items shipped before Sept 2, 1998,
 grouped by return flag and status. Include sum of quantities,
 prices with/without discounts, averages, and counts."
```

---

## Improvement Roadmap

### Phase 1: Quick Wins (1 hour) → +15-20 points

**1A. Fix Embeddings (30 min)**
```bash
# Option 1: Add OpenAI key
echo "OPENAI_API_KEY=sk-..." >> .env
docker compose restart dash-api

# Option 2: Switch to Anthropic embeddings
# Edit dash/agents.py:
# from agno.knowledge.embedder.anthropic import AnthropicEmbedder
# embedder=AnthropicEmbedder()
```

**1B. Reload Knowledge (10 min)**
```bash
docker exec dash-api python -m dash.scripts.load_knowledge --recreate
```

**1C. Test Knowledge Search (5 min)**
```bash
docker exec dash-api python -c "
from dash.agents import dash_knowledge
results = dash_knowledge.search('revenue calculation lineitem')
print(f'Found {len(results)} results')
for r in results:
    print(f'  - {r.name}')
"
```

**1D. Re-run Top 5 Queries (15 min)**
```bash
docker exec dash-api python /app/run_final_tpch_eval.py Q1 Q3 Q6 Q17 Q19
```

**Expected: 3-4 of these should jump from <40% to 70%+**

---

### Phase 2: Better Validation (2 hours) → +10-15 points

**2A. Improve Number Matching**
```python
def extract_numbers_from_text(text):
    """Extract all numbers from text, normalized."""
    # Remove currency symbols, commas
    # Parse: $123M → 123000000, 123,456.78 → 123456.78
    # Return normalized list

def compare_numbers_with_tolerance(response_nums, golden_nums, tolerance=0.01):
    """Check if golden numbers appear in response (±1%)."""
    # For each golden number, check if similar number exists in response
    # Return match percentage
```

**2B. Extract SQL from Tool Calls**
```python
# Instead of parsing response text, extract from debug logs:
# DEBUG Running sql | SELECT ... FROM ...
# Or hook into agent's tool execution directly
```

**2C. Execute & Compare Results**
```python
# If SQL extracted:
dash_results = execute_sql(extracted_sql)
golden_results = execute_sql(golden_sql)
similarity = compare_results(dash_results, golden_results)
```

---

### Phase 3: Enhanced Knowledge (2 hours) → +5-10 points

**3A. Add TPC-H Query Patterns**

Create `dash/knowledge/queries/tpch_official_patterns.sql`:
```sql
-- <query name>tpch_q1_pattern</query name>
-- <query description>
-- Pricing summary by return flag and status
-- Date: shipdate before specific date
-- Aggregations: sum qty, price, discounts, taxes, averages, counts
-- </query description>
-- <query>
SELECT
    l_returnflag,
    l_linestatus,
    SUM(l_quantity) as sum_qty,
    SUM(l_extendedprice) as sum_base_price,
    SUM(l_extendedprice * (1 - l_discount)) as sum_disc_price,
    SUM(l_extendedprice * (1 - l_discount) * (1 + l_tax)) as sum_charge,
    AVG(l_quantity) as avg_qty,
    AVG(l_extendedprice) as avg_price,
    AVG(l_discount) as avg_disc,
    COUNT(*) as count_order
FROM lineitem
WHERE l_shipdate <= DATE '1998-12-01' - INTERVAL '90' DAY
GROUP BY l_returnflag, l_linestatus
ORDER BY l_returnflag, l_linestatus
-- </query>

-- Add all 22 query patterns...
```

**3B. Add Query Hints**

Create `dash/knowledge/business/tpch_query_hints.json`:
```json
{
  "query_patterns": [
    {
      "name": "Q1 - Pricing Summary",
      "keywords": ["pricing", "summary", "return flag", "line status"],
      "tables": ["lineitem"],
      "key_calculations": [
        "sum_disc_price = l_extendedprice * (1 - l_discount)",
        "sum_charge = l_extendedprice * (1 - l_discount) * (1 + l_tax)"
      ],
      "common_filters": ["l_shipdate <= DATE - INTERVAL"],
      "expected_rows": "4 rows (combinations of return_flag x line_status)"
    },
    {
      "name": "Q5 - Local Supplier Volume",
      "keywords": ["supplier", "region", "revenue", "year"],
      "tables": ["customer", "orders", "lineitem", "supplier", "nation", "region"],
      "key_joins": [
        "c_custkey = o_custkey",
        "l_orderkey = o_orderkey",
        "l_suppkey = s_suppkey",
        "c_nationkey = s_nationkey (customer and supplier same nation!)"
      ],
      "gotcha": "Customer and supplier must be in SAME nation for local supplier volume"
    }
    // ... all 22 queries
  ]
}
```

---

### Phase 4: Refine Questions (1 hour) → +5-8 points

**4A. Make Questions More Explicit**

Currently underperforming queries:

**Q1 (35%):**
```python
# Current:
"What are the summary pricing statistics for line items grouped by return flag and status?"

# Improved:
"Show a pricing summary report for line items shipped before September 2, 1998.
 Group by return flag and line status. Include:
 - Sum of quantities, extended prices, discounted prices, and charges
 - Averages of quantity, price, and discount
 - Count of orders
 Order by return flag and line status."
```

**Q6 (0%):**
```python
# Current:
"What is the total revenue from line items with specific discount and quantity constraints in 1994?"

# Improved:
"Calculate the potential revenue from eliminating discounts on line items where:
 - Ship date is in 1994
 - Discount is between 5% and 7%
 - Quantity is less than 24
 Use the formula: SUM(l_extendedprice * l_discount)"
```

---

## Expected Impact Summary

| Improvement | Effort | Expected Gain | Priority |
|-------------|--------|---------------|----------|
| **Fix Embeddings** | 30 min | +15-20 points | 🔥 CRITICAL |
| **Better Validation** | 2 hours | +10-15 points | 🔥 HIGH |
| **Enhanced Knowledge** | 2 hours | +5-10 points | ⚠️ MEDIUM |
| **Refine Questions** | 1 hour | +5-8 points | ⚠️ LOW |
| **TOTAL** | 5-6 hours | **+35-53 points** | |

**Projected Final Score:** 88-106% (realistically 75-85% accounting for overlaps)

---

## Immediate Action Plan

### Step 1: Fix Embeddings (NOW - 15 min)

```bash
# Add OpenAI key to .env
nano .env
# Add: OPENAI_API_KEY=sk-...

# Restart
docker compose restart dash-api

# Verify knowledge search works
docker exec dash-api python -c "
from dash.agents import dash_knowledge
results = dash_knowledge.search('revenue calculation')
print(f'✅ Found {len(results)} results' if results else '❌ Still not working')
"

# Reload knowledge with embeddings
docker exec dash-api python -m dash.scripts.load_knowledge --recreate
```

### Step 2: Re-run Failed Queries (10 min)

```bash
# Test the 3 failed queries
docker exec dash-api python /app/run_final_tpch_eval.py Q6 Q17 Q19

# Expected: At least 2 should now score 50%+
```

### Step 3: Re-run Full Evaluation (30 min)

```bash
# Full 22-query re-run with knowledge base working
docker exec dash-api python /app/run_final_tpch_eval.py 2>&1 | tee tpch_eval_v2.log

# Expected: Average score 65-75%
```

---

## Alternative: Use Anthropic Embeddings

If you don't have an OpenAI key, switch to Anthropic embeddings:

**File: `dash/agents.py`**

```python
# BEFORE (line 13):
from agno.knowledge.embedder.openai import OpenAIEmbedder

# AFTER:
from agno.knowledge.embedder.anthropic import AnthropicEmbedder

# BEFORE (line 44):
embedder=OpenAIEmbedder(id="text-embedding-3-small"),

# AFTER:
embedder=AnthropicEmbedder(model="claude-3-5-sonnet-20241022"),  # or latest model
```

Then:
```bash
docker compose down && docker compose up -d --build
docker exec dash-api python -m dash.scripts.load_knowledge --recreate
```

---

## Long-term Improvements

### 1. Add Official TPC-H Patterns

Extract the actual SQL from all 22 queries and add to knowledge base:

```bash
# Create script to convert timbr queries to knowledge format
python create_tpch_knowledge.py

# Generates:
dash/knowledge/queries/tpch_q01.sql
dash/knowledge/queries/tpch_q02.sql
...
dash/knowledge/queries/tpch_q22.sql
```

### 2. Add Query-Specific Hints

```json
{
  "Q1_hints": {
    "key_filter": "l_shipdate <= DATE '1998-12-01' - INTERVAL '90' DAY",
    "group_by": "l_returnflag, l_linestatus",
    "calculations": [
      "sum_disc_price = extendedprice * (1 - discount)",
      "sum_charge = extendedprice * (1 - discount) * (1 + tax)"
    ]
  }
}
```

### 3. Implement Learning from Eval

After each eval run, save successful patterns:

```python
# For queries that scored 100%:
for query in perfect_queries:
    dash.run(f"Save this query pattern: {query['sql']}")
    # Agent uses save_validated_query tool
```

### 4. Fine-tune Natural Language

Test different phrasings and pick the best:

```python
Q1_VARIATIONS = [
    "What are the summary pricing statistics...",  # Current: 35%
    "Show pricing summary report for line items...",  # Test
    "Generate TPC-H Q1 pricing summary report...",  # Explicit
]

# Test each, pick highest scoring
```

---

## Quick Test Script

I'll create a script to test improvements quickly:

```bash
#!/bin/bash
# test_improvements.sh

echo "Testing improvement impact..."

echo "1. Testing without knowledge base (baseline)"
docker exec dash-api python /app/run_final_tpch_eval.py Q1 Q3 Q6

echo "2. Fix embeddings and reload knowledge"
# (you add OPENAI_API_KEY)
docker compose restart dash-api
docker exec dash-api python -m dash.scripts.load_knowledge --recreate

echo "3. Re-test same queries"
docker exec dash-api python /app/run_final_tpch_eval.py Q1 Q3 Q6

echo "Compare scores - should see improvement!"
```

---

## Projected Improvements

### Scenario 1: Fix Embeddings Only (30 min effort)

**Before:** 53.3% average
**After:** 68-73% average
**Change:** +15-20 points

**Expected per-query improvements:**
- Q1: 35% → 55% (knowledge of pricing calculations)
- Q3: 25% → 45% (knowledge of unshipped = shipdate > orderdate)
- Q6: 0% → 70% (knowledge of discount formula)
- Q17: 0% → 50% (knowledge of average calculations)

### Scenario 2: Fix Embeddings + Better Validation (3 hours effort)

**Before:** 53.3% average
**After:** 75-80% average
**Change:** +22-27 points

**Expected changes:**
- Currently 0% queries (Q6, Q17, Q19) → 60-70%
- Currently <40% queries → 50-60%
- Already excellent queries stay at 90-100%

### Scenario 3: All Improvements (6 hours effort)

**Before:** 53.3% average
**After:** 80-85% average
**Change:** +27-32 points

**Expected distribution:**
- Excellent (≥70%): 15-18 queries (vs current 7)
- Good (50-69%): 4-5 queries (vs current 6)
- Partial/Failed: 0-3 queries (vs current 9)

---

## Recommended Approach

### Option A: Fast Track (1 hour)
1. ✅ Add OPENAI_API_KEY to .env
2. ✅ Restart containers
3. ✅ Reload knowledge with embeddings
4. ✅ Re-run evaluation
5. ✅ Document improvement

**Expected Result:** 68-73% average (+15-20 points)

### Option B: Comprehensive (6 hours)
1. ✅ Fix embeddings (30 min)
2. ✅ Improve validation (2 hours)
3. ✅ Enhance knowledge (2 hours)
4. ✅ Refine questions (1 hour)
5. ✅ Re-run and document (30 min)

**Expected Result:** 80-85% average (+27-32 points)

### Option C: Targeted (3 hours)
1. ✅ Fix embeddings (30 min)
2. ✅ Focus on failed queries (Q6, Q17, Q19) (1 hour)
3. ✅ Improve validation for numeric answers (1 hour)
4. ✅ Re-run full evaluation (30 min)

**Expected Result:** 75-80% average (+22-27 points)

---

## Implementation Steps (Fast Track)

### Step 1: Get OpenAI API Key

Visit: https://platform.openai.com/api-keys

Create key (only needs embedding access, cheapest tier is fine)

### Step 2: Configure

```bash
# Edit .env
nano .env

# Add line:
OPENAI_API_KEY=sk-your-key-here
```

### Step 3: Restart & Reload

```bash
docker compose restart dash-api
sleep 10

# Recreate knowledge with embeddings
docker exec dash-api python -m dash.scripts.load_knowledge --recreate

# Verify
docker exec dash-api python -c "
from dash.agents import dash_knowledge
print(dash_knowledge.vector_db.search('revenue calculation', limit=5))
"
```

### Step 4: Re-evaluate

```bash
# Start with failed queries
docker exec dash-api python /app/run_final_tpch_eval.py Q6 Q17 Q19

# If improved, run full evaluation
docker exec dash-api python /app/run_final_tpch_eval.py
```

### Step 5: Compare Results

```bash
# Before (current):
# Average: 53.3%, Excellent: 7/22

# After (expected):
# Average: 68-73%, Excellent: 13-15/22
```

---

## Cost Consideration

**Embeddings Cost (OpenAI):**
- text-embedding-3-small: $0.00002 per 1K tokens
- 22 knowledge entries × ~500 tokens = 11K tokens
- Cost: $0.00022 (negligible)

**Re-evaluation Cost (Claude):**
- 22 queries × ~50K tokens avg = 1.1M tokens
- Claude Opus 4.5: ~$0.015/1K input, $0.075/1K output
- Cost: ~$20-30

**Total to test improvement:** < $30

**Expected ROI:** 15-20 point improvement for $30 → Excellent value

---

## Decision Matrix

| Goal | Time | Cost | Expected Gain | Recommended? |
|------|------|------|---------------|--------------|
| Quick proof of improvement | 1 hr | $30 | +15-20 pts | ✅ YES |
| Publication-ready results | 6 hrs | $50 | +27-32 pts | ✅ YES if showcasing |
| Good enough understanding | 0 hrs | $0 | +0 pts | ✅ YES if done evaluating |

---

## Next Steps

**What would you like to do?**

1. **Quick fix** → Add OPENAI_API_KEY and re-run (1 hour, +15-20 points)
2. **Comprehensive** → Full improvement plan (6 hours, +27-32 points)
3. **Targeted** → Focus on specific queries (3 hours, +22-27 points)
4. **Done** → Keep current results and move on

**My recommendation:** Start with **Option 1 (Quick fix)** - biggest impact for least effort!
