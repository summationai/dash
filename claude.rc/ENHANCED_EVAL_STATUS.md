# Enhanced TPC-H Evaluation - Live Status

**Started:** 2026-02-04
**Model:** Claude Opus 4.5
**Dataset:** TPC-H SF1 (8.5M rows in DuckDB)
**Status:** 🔄 **IN PROGRESS**

---

## Evaluation Strategy

### Original Plan
❌ Extract SQL from response text → Compare to golden SQL → Execute both → Compare results

**Problem:** Claude uses tools to execute SQL (correct agent behavior) rather than showing SQL in text

### Enhanced Plan
✅ Pre-compute golden results → Run Dash → Validate answers appear in response

**Advantage:** Tests if agent gets the right answer (the actual goal) regardless of SQL approach

---

## Progress

```
Precomputing golden results: ✅ COMPLETE
Running 22 TPC-H queries:     🔄 IN PROGRESS (Query 8/22, ~36%)
Expected completion:           ~5-7 minutes
```

---

## Queries Being Tested

| ID | Name | Complexity | Golden Rows | Status |
|----|------|------------|-------------|--------|
| Q1 | Pricing Summary Report | Medium | 4 | ✅ |
| Q2 | Minimum Cost Supplier | High | Varies | ✅ |
| Q3 | Shipping Priority | Medium | 10 | ✅ |
| Q4 | Order Priority Checking | Medium | 5 | ✅ |
| Q5 | Local Supplier Volume | High | 5 | ✅ |
| Q6 | Forecasting Revenue Change | Low | 1 | ✅ |
| Q7 | Volume Shipping | High | Varies | ✅ |
| Q8 | National Market Share | High | Varies | 🔄 Current |
| Q9-Q22 | ... | ... | ... | ⏳ Pending |

---

## Preliminary Results (Queries 1-7)

Based on partial output:

**Answer Correctness:**
- All queries generating comprehensive responses
- Insights include tables, analysis, and recommendations
- Response length: 1,000-2,500 characters per query
- Average response time: ~15-25 seconds

**Key Observations:**
1. ✅ Claude correctly identifies TPC-H queries by name (e.g., "This is TPC-H Query 6")
2. ✅ Proper revenue calculations using discount and tax formulas
3. ✅ Multi-table joins executed correctly
4. ⚠️  Embedding errors (needs OpenAI key for vector search) but doesn't block execution
5. ✅ Comprehensive insights beyond raw data

---

## Technical Notes

### Configuration
- **Model:** claude-opus-4-5-20251101 via Anthropic API
- **Data:** DuckDB with TPC-H SF1
- **Vector DB:** PgVector (knowledge + learnings)
- **Embeddings:** OpenAIEmbedder (requires OPENAI_API_KEY for knowledge search)

### Known Issues
1. **Embedding failures:** Knowledge base search fails without OPENAI_API_KEY
   - **Impact:** Agent can't retrieve TPC-H knowledge/patterns
   - **Workaround:** Agent still functions using base instructions
   - **Fix:** Add OPENAI_API_KEY for embeddings (separate from Claude API)

2. **DuckDB connection conflicts:** Avoided by pre-computing golden results

3. **SQL extraction:** Agent uses tools (correct!) so SQL not always in text response

---

## Sample Response Quality

### Query 6: Forecasting Revenue Change

**Question:** "What is the total revenue from line items with specific discount and quantity constraints in 1994?"

**Dash Response (excerpt):**
```
## Revenue from Discounted Line Items in 1994

| Metric | Value |
|:-------|------:|
| **Potential Revenue (from eliminating discounts)** | **$123,141,078.23** |
| Base Price of Matching Items | $2.05B |
| Matching Line Items | 114,160 |
| Average Discount | 6.0% |
| Average Quantity | 12.0 units |

### Key Insights

1. **$123M Revenue Opportunity**: If discounts in this range (5-7%) were
   eliminated for small quantity orders (<24 units), the company could have
   captured an additional **$123.1M in revenue** in 1994.

2. **Targeted Segment**: This represents only **12.5% of all 1994 line
   items** (114K out of 909K), but accounts for **7.1% of all discounts
   given** ($123M of $1.74B total).

... (continues with detailed analysis)
```

**Assessment:** ⭐⭐⭐⭐⭐
- ✅ Correct calculation
- ✅ Comprehensive insights
- ✅ Business context
- ✅ Formatted output
- ✅ Identified as "TPC-H Query 6"

---

## Next Steps

1. **Wait for full evaluation to complete** (~5 more minutes)
2. **Analyze all 22 results**
3. **Fix embedding issue** (add OPENAI_API_KEY for vector search)
4. **Re-run with knowledge base** (should improve performance)
5. **Document final findings**

---

**Last Updated:** 2026-02-04 03:28 (Auto-updating as evaluation runs)
