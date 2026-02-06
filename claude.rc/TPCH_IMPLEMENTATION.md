# TPC-H Implementation Guide

This is the step-by-step implementation guide to convert Dash from F1/PostgreSQL to TPC-H/DuckDB.

## Step 1: Generate TPC-H Data (5 min)

```bash
# Make sure you're in the dash directory
cd /Users/rc/code-playground/data/dash

# Create data directory
mkdir -p data

# Generate TPC-H SF1 data using DuckDB
duckdb data/tpch_sf1.db << 'EOF'
INSTALL tpch;
LOAD tpch;
CALL dbgen(sf=1);

-- Verify
SELECT
  'region' as table_name, COUNT(*) as row_count FROM region
UNION ALL SELECT 'nation', COUNT(*) FROM nation
UNION ALL SELECT 'supplier', COUNT(*) FROM supplier
UNION ALL SELECT 'part', COUNT(*) FROM part
UNION ALL SELECT 'partsupp', COUNT(*) FROM partsupp
UNION ALL SELECT 'customer', COUNT(*) FROM customer
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'lineitem', COUNT(*) FROM lineitem;

-- Show sample data
SELECT * FROM region;
SELECT * FROM nation LIMIT 10;
EOF
```

**Verify:** You should see ~8.5M total rows and sample data from region/nation tables.

---

## Step 2: Add DuckDB Dependencies

**File: `requirements.txt`**

Add these lines:

```txt
duckdb>=0.10.0
duckdb-engine>=0.11.0
```

---

## Step 3: Create DuckDB Connection Module

**File: `db/duckdb_url.py`** (create new file)

```python
"""
DuckDB URL Builder
==================

Build DuckDB connection URL for TPC-H data.
"""

from os import getenv
from pathlib import Path


def build_duckdb_url() -> str:
    """Build DuckDB URL for TPC-H data.

    Returns:
        DuckDB connection URL in SQLAlchemy format.
    """
    # Get path from env or use default
    db_path = getenv("DUCKDB_PATH", "data/tpch_sf1.db")

    # Convert to absolute path
    db_path = Path(db_path).resolve()

    # Verify file exists
    if not db_path.exists():
        print(f"Warning: DuckDB file not found at {db_path}")

    # DuckDB SQLAlchemy URL format: duckdb:///path/to/file.db
    return f"duckdb:///{db_path}"


# Export the URL
duckdb_url = build_duckdb_url()
```

---

## Step 4: Update Agent Configuration

**File: `dash/agents.py`**

### Change 1: Import duckdb_url (line 29)

```python
# BEFORE:
from db import db_url, get_postgres_db

# AFTER:
from db import db_url, get_postgres_db
from db.duckdb_url import duckdb_url
```

### Change 2: Update introspect_schema tool (line 66)

```python
# BEFORE:
introspect_schema = create_introspect_schema_tool(db_url)

# AFTER:
introspect_schema = create_introspect_schema_tool(duckdb_url)
```

### Change 3: Update SQLTools (line 69)

```python
# BEFORE:
base_tools: list = [
    SQLTools(db_url=db_url),
    save_validated_query,
    introspect_schema,
    MCPTools(url=f"https://mcp.exa.ai/mcp?exaApiKey={getenv('EXA_API_KEY', '')}&tools=web_search_exa"),
]

# AFTER:
base_tools: list = [
    SQLTools(db_url=duckdb_url),  # ← Changed to duckdb_url
    save_validated_query,
    introspect_schema,
    MCPTools(url=f"https://mcp.exa.ai/mcp?exaApiKey={getenv('EXA_API_KEY', '')}&tools=web_search_exa"),
]
```

### Change 4: Update instructions (line 79+)

Update the SEMANTIC_MODEL and BUSINESS_CONTEXT to reference TPC-H instead of F1:

```python
INSTRUCTIONS = f"""\
You are Dash, a self-learning data agent that provides **insights**, not just query results.

## Your Purpose

You are the user's data analyst working with the TPC-H benchmark dataset — a standard business
database containing customers, orders, parts, and suppliers.

You don't just fetch data. You interpret it, contextualize it, and explain what it means.

... (rest of instructions)
"""
```

---

## Step 5: Create TPC-H Knowledge Files

Create these files in the knowledge directory:

```bash
# Create directory structure if needed
mkdir -p dash/knowledge/tables
mkdir -p dash/knowledge/queries
mkdir -p dash/knowledge/business

# Remove old F1 knowledge
rm dash/knowledge/tables/*.json
rm dash/knowledge/queries/*.sql
rm dash/knowledge/business/*.json
```

### Create Table Metadata

**File: `dash/knowledge/tables/lineitem.json`**

```json
{
  "table_name": "lineitem",
  "table_description": "Order line items. Most important table for revenue analysis with ~6M rows at SF1.",
  "use_cases": [
    "Revenue analysis",
    "Part sales tracking",
    "Supplier performance",
    "Shipping analysis"
  ],
  "data_quality_notes": [
    "Revenue calculation: l_extendedprice * (1 - l_discount) * (1 + l_tax)",
    "l_shipdate <= l_receiptdate always",
    "l_returnflag: 'R' (returned), 'A' (available), 'N' (not returned)",
    "l_linestatus: 'O' (open), 'F' (filled)",
    "l_discount ranges from 0.00 to 0.10",
    "l_tax ranges from 0.00 to 0.08"
  ],
  "table_columns": [
    {"name": "l_orderkey", "type": "INTEGER", "description": "Foreign key to orders"},
    {"name": "l_partkey", "type": "INTEGER", "description": "Foreign key to part"},
    {"name": "l_suppkey", "type": "INTEGER", "description": "Foreign key to supplier"},
    {"name": "l_linenumber", "type": "INTEGER", "description": "Line number (1-7)"},
    {"name": "l_quantity", "type": "DECIMAL(15,2)", "description": "Quantity ordered"},
    {"name": "l_extendedprice", "type": "DECIMAL(15,2)", "description": "Extended price"},
    {"name": "l_discount", "type": "DECIMAL(15,2)", "description": "Discount (0.00-0.10)"},
    {"name": "l_tax", "type": "DECIMAL(15,2)", "description": "Tax (0.00-0.08)"},
    {"name": "l_returnflag", "type": "VARCHAR(1)", "description": "R/A/N"},
    {"name": "l_linestatus", "type": "VARCHAR(1)", "description": "O/F"},
    {"name": "l_shipdate", "type": "DATE", "description": "Ship date"},
    {"name": "l_commitdate", "type": "DATE", "description": "Commit date"},
    {"name": "l_receiptdate", "type": "DATE", "description": "Receipt date"},
    {"name": "l_shipinstruct", "type": "VARCHAR", "description": "Ship instructions"},
    {"name": "l_shipmode", "type": "VARCHAR", "description": "TRUCK/MAIL/SHIP/AIR/FOB/RAIL/REG AIR"},
    {"name": "l_comment", "type": "VARCHAR", "description": "Comment"}
  ]
}
```

**File: `dash/knowledge/tables/orders.json`**

```json
{
  "table_name": "orders",
  "table_description": "Customer orders with 1.5M rows at SF1.",
  "use_cases": [
    "Order volume analysis",
    "Revenue reporting",
    "Order status tracking"
  ],
  "data_quality_notes": [
    "o_orderdate ranges from 1992-01-01 to 1998-12-31",
    "o_orderstatus: 'O' (open), 'F' (filled), 'P' (partial) - single character",
    "o_orderpriority: 1-URGENT, 2-HIGH, 3-MEDIUM, 4-NOT SPECIFIED, 5-LOW",
    "o_totalprice is sum of lineitem extended prices for this order"
  ],
  "table_columns": [
    {"name": "o_orderkey", "type": "INTEGER", "description": "Unique order ID"},
    {"name": "o_custkey", "type": "INTEGER", "description": "Foreign key to customer"},
    {"name": "o_orderstatus", "type": "VARCHAR(1)", "description": "O/F/P"},
    {"name": "o_totalprice", "type": "DECIMAL(15,2)", "description": "Total price"},
    {"name": "o_orderdate", "type": "DATE", "description": "Order date"},
    {"name": "o_orderpriority", "type": "VARCHAR", "description": "Priority level"},
    {"name": "o_clerk", "type": "VARCHAR", "description": "Clerk name"},
    {"name": "o_shippriority", "type": "INTEGER", "description": "Ship priority"},
    {"name": "o_comment", "type": "VARCHAR", "description": "Comment"}
  ]
}
```

**File: `dash/knowledge/tables/customer.json`**

```json
{
  "table_name": "customer",
  "table_description": "Customer information with 150K customers at SF1.",
  "use_cases": [
    "Customer segmentation",
    "Market analysis",
    "Customer orders"
  ],
  "data_quality_notes": [
    "c_acctbal can be negative (credit balance)",
    "c_mktsegment has exactly 5 values: AUTOMOBILE, BUILDING, FURNITURE, MACHINERY, HOUSEHOLD",
    "Customers evenly distributed across 25 nations"
  ],
  "table_columns": [
    {"name": "c_custkey", "type": "INTEGER", "description": "Unique customer ID"},
    {"name": "c_name", "type": "VARCHAR", "description": "Customer name"},
    {"name": "c_address", "type": "VARCHAR", "description": "Address"},
    {"name": "c_nationkey", "type": "INTEGER", "description": "Foreign key to nation"},
    {"name": "c_phone", "type": "VARCHAR", "description": "Phone"},
    {"name": "c_acctbal", "type": "DECIMAL(15,2)", "description": "Account balance"},
    {"name": "c_mktsegment", "type": "VARCHAR", "description": "Market segment"},
    {"name": "c_comment", "type": "VARCHAR", "description": "Comment"}
  ]
}
```

*(Continue with region.json, nation.json, supplier.json, part.json, partsupp.json - see TPCH_SETUP.md for full details)*

### Create Query Patterns

**File: `dash/knowledge/queries/tpch_common.sql`**

```sql
-- <query name>total_revenue</query name>
-- <query description>
-- Calculate total revenue using TPC-H standard formula.
-- Revenue = l_extendedprice * (1 - l_discount) * (1 + l_tax)
-- </query description>
-- <query>
SELECT
    SUM(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS total_revenue
FROM lineitem
-- </query>


-- <query name>revenue_by_year</query name>
-- <query description>
-- Annual revenue trends from lineitem.
-- </query description>
-- <query>
SELECT
    EXTRACT(YEAR FROM l_shipdate) AS year,
    SUM(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS revenue
FROM lineitem
GROUP BY EXTRACT(YEAR FROM l_shipdate)
ORDER BY year
-- </query>


-- <query name>top_customers</query name>
-- <query description>
-- Top 10 customers by revenue.
-- </query description>
-- <query>
SELECT
    c.c_custkey,
    c.c_name,
    c.c_mktsegment,
    SUM(l.l_extendedprice * (1 - l.l_discount)) AS revenue
FROM customer c
JOIN orders o ON c.c_custkey = o.o_custkey
JOIN lineitem l ON o.o_orderkey = l.l_orderkey
GROUP BY c.c_custkey, c.c_name, c.c_mktsegment
ORDER BY revenue DESC
LIMIT 10
-- </query>


-- <query name>regional_revenue</query name>
-- <query description>
-- Revenue by geographic region.
-- </query description>
-- <query>
SELECT
    r.r_name AS region,
    SUM(l.l_extendedprice * (1 - l.l_discount)) AS revenue
FROM region r
JOIN nation n ON r.r_regionkey = n.n_regionkey
JOIN customer c ON n.n_nationkey = c.c_nationkey
JOIN orders o ON c.c_custkey = o.o_custkey
JOIN lineitem l ON o.o_orderkey = l.l_orderkey
GROUP BY r.r_name
ORDER BY revenue DESC
-- </query>
```

### Create Business Rules

**File: `dash/knowledge/business/tpch_metrics.json`**

```json
{
  "metrics": [
    {
      "name": "Revenue",
      "definition": "Extended price with discount and tax applied",
      "calculation": "l_extendedprice * (1 - l_discount) * (1 + l_tax)"
    },
    {
      "name": "Net Revenue",
      "definition": "Revenue after discount, before tax",
      "calculation": "l_extendedprice * (1 - l_discount)"
    }
  ],
  "common_gotchas": [
    {
      "issue": "Revenue calculation",
      "solution": "Always use: l_extendedprice * (1 - l_discount) * (1 + l_tax)"
    },
    {
      "issue": "Order status",
      "solution": "o_orderstatus is single character: O/F/P"
    },
    {
      "issue": "Market segments",
      "solution": "Only 5 values: AUTOMOBILE, BUILDING, FURNITURE, MACHINERY, HOUSEHOLD"
    }
  ]
}
```

---

## Step 6: Update Docker Configuration

**File: `compose.yaml`**

Update the dash-api service to mount the data directory:

```yaml
dash-api:
  # ... existing configuration ...
  volumes:
    - .:/app
    - dash-data:/data
    - ./data:/app/data  # ← Add this line
  environment:
    # ... existing env vars ...
    DUCKDB_PATH: /app/data/tpch_sf1.db  # ← Add this
```

**File: `.env`**

Update environment variables:

```bash
# Required
OPENAI_API_KEY=sk-***

# DuckDB Configuration (NEW)
DUCKDB_PATH=/app/data/tpch_sf1.db

# PostgreSQL (for agent metadata and vectors - keep as is)
DB_HOST=dash-db
DB_PORT=5432
DB_USER=ai
DB_PASS=ai
DB_DATABASE=ai
```

---

## Step 7: Build and Test

```bash
# Stop existing containers
docker compose down

# Rebuild with new dependencies
docker compose up -d --build

# Wait for services to be ready
sleep 10

# Test DuckDB connection
docker exec -it dash-api python -c "
from db.duckdb_url import duckdb_url
print(f'DuckDB URL: {duckdb_url}')

import duckdb
conn = duckdb.connect('/app/data/tpch_sf1.db', read_only=True)
print('\nTable counts:')
print(conn.execute('SELECT COUNT(*) FROM lineitem').fetchone())
print('Lineitem sample:')
print(conn.execute('SELECT * FROM lineitem LIMIT 3').fetchdf())
"

# Load TPC-H knowledge
docker exec -it dash-api python -m dash.scripts.load_knowledge

# Verify knowledge loaded
docker exec -it dash-db psql -U ai -d ai -c "SELECT COUNT(*) FROM dash_knowledge;"
```

---

## Step 8: Test Queries

### Via Agno UI

1. Open https://os.agno.com
2. Add OS → Local → http://localhost:8000
3. Connect

Try these queries:

```
1. What is the total revenue?

2. Show revenue by year

3. Which customer has the highest revenue?

4. What are the top 5 regions by revenue?

5. How many orders are in each status?
```

### Via CLI

```bash
docker exec -it dash-api python -c "
from dash.agents import dash
dash.print_response('What is the total revenue?', stream=True)
"
```

---

## Step 9: Create TPC-H Evaluation Suite

**File: `dash/evals/tpch_test_cases.py`** (create new file)

```python
"""
TPC-H test cases for evaluating Dash.
"""

from dataclasses import dataclass


@dataclass
class TestCase:
    """A test case for evaluating Dash."""
    question: str
    expected_strings: list[str]
    category: str
    golden_sql: str | None = None


TPCH_TEST_CASES: list[TestCase] = [
    # Basic queries
    TestCase(
        question="What is the total revenue?",
        expected_strings=["revenue"],
        category="basic",
        golden_sql="""
            SELECT SUM(l_extendedprice * (1 - l_discount) * (1 + l_tax)) as revenue
            FROM lineitem
        """,
    ),
    TestCase(
        question="How many customers are there?",
        expected_strings=["150000", "150,000"],
        category="basic",
        golden_sql="SELECT COUNT(*) FROM customer",
    ),
    TestCase(
        question="How many orders are there?",
        expected_strings=["1500000", "1,500,000", "1.5"],
        category="basic",
        golden_sql="SELECT COUNT(*) FROM orders",
    ),

    # Aggregation
    TestCase(
        question="Show revenue by year",
        expected_strings=["1992", "1993", "revenue"],
        category="aggregation",
        golden_sql="""
            SELECT
                EXTRACT(YEAR FROM l_shipdate) AS year,
                SUM(l_extendedprice * (1 - l_discount)) AS revenue
            FROM lineitem
            GROUP BY EXTRACT(YEAR FROM l_shipdate)
            ORDER BY year
        """,
    ),
    TestCase(
        question="Which market segment has the most customers?",
        expected_strings=["AUTOMOBILE", "BUILDING", "FURNITURE"],
        category="aggregation",
        golden_sql="""
            SELECT c_mktsegment, COUNT(*) as count
            FROM customer
            GROUP BY c_mktsegment
            ORDER BY count DESC
            LIMIT 1
        """,
    ),

    # Complex joins
    TestCase(
        question="What is the revenue by region?",
        expected_strings=["AMERICA", "ASIA", "EUROPE", "revenue"],
        category="complex",
        golden_sql="""
            SELECT
                r.r_name AS region,
                SUM(l.l_extendedprice * (1 - l.l_discount)) AS revenue
            FROM region r
            JOIN nation n ON r.r_regionkey = n.n_regionkey
            JOIN customer c ON n.n_nationkey = c.c_nationkey
            JOIN orders o ON c.c_custkey = o.o_custkey
            JOIN lineitem l ON o.o_orderkey = l.l_orderkey
            GROUP BY r.r_name
            ORDER BY revenue DESC
        """,
    ),

    # Data quality tests
    TestCase(
        question="How many orders have status 'F'?",
        expected_strings=["status", "F"],
        category="data_quality",
        golden_sql="""
            SELECT COUNT(*) FROM orders WHERE o_orderstatus = 'F'
        """,
    ),
]
```

---

## Verification Checklist

- [ ] TPC-H data generated (8 tables, ~8.5M rows)
- [ ] Dependencies added (duckdb, duckdb-engine)
- [ ] `db/duckdb_url.py` created
- [ ] `dash/agents.py` updated (3 changes)
- [ ] Table metadata created (8 JSON files)
- [ ] Query patterns created (tpch_common.sql)
- [ ] Business rules created (tpch_metrics.json)
- [ ] Docker config updated (volume mount)
- [ ] Environment variables set (DUCKDB_PATH)
- [ ] Containers rebuilt and started
- [ ] DuckDB connection tested
- [ ] Knowledge loaded to PgVector
- [ ] Sample queries work
- [ ] Agno UI connected

---

## Troubleshooting

### "No module named 'duckdb'"

```bash
# Rebuild containers with new dependencies
docker compose down
docker compose up -d --build
```

### "DuckDB file not found"

```bash
# Check file exists
ls -lh data/tpch_sf1.db

# Verify mount in container
docker exec -it dash-api ls -lh /app/data/

# Regenerate if needed
duckdb data/tpch_sf1.db "INSTALL tpch; LOAD tpch; CALL dbgen(sf=1);"
```

### "Cannot connect to DuckDB"

```bash
# Test connection manually
docker exec -it dash-api python -c "
import duckdb
conn = duckdb.connect('/app/data/tpch_sf1.db', read_only=True)
print(conn.execute('SELECT 1').fetchone())
"
```

### Knowledge not loading

```bash
# Check knowledge files exist
ls dash/knowledge/tables/
ls dash/knowledge/queries/
ls dash/knowledge/business/

# Recreate knowledge base
docker exec -it dash-api python -m dash.scripts.load_knowledge --recreate
```

---

## Next Steps

1. ✅ Complete implementation (Steps 1-9)
2. Run comprehensive evaluation (TPCH_SETUP.md)
3. Test with TPC-H official 22 queries
4. Compare performance vs PostgreSQL
5. Document findings

---

## Summary of Changes

| Component | Change | Impact |
|-----------|--------|--------|
| Data Source | PostgreSQL → DuckDB | Query execution |
| Dataset | F1 (5 tables, 100K rows) → TPC-H (8 tables, 8.5M rows) | Scale, complexity |
| Knowledge Files | Sports stats → Business transactions | Domain |
| Vector Store | No change (still PgVector) | Knowledge retrieval |
| Agent Metadata | No change (still PostgreSQL) | Runs, sessions |

**Result:** Dash now queries TPC-H in DuckDB while maintaining its learning capabilities in PostgreSQL.
