# TPC-H SF1 Setup with DuckDB

## Overview

This guide modifies Dash to use **TPC-H Scale Factor 1** data in **DuckDB** instead of the F1 PostgreSQL dataset.

### Architecture Changes

```
┌─────────────────────────────────────────────────────────┐
│                  ORIGINAL SETUP                         │
├─────────────────────────────────────────────────────────┤
│ Data Source:    PostgreSQL (F1 dataset)                │
│ Vector Store:   PgVector (knowledge + learnings)       │
│ Agent Metadata: PostgreSQL (sessions, runs)            │
└─────────────────────────────────────────────────────────┘

                          ↓ CHANGES TO ↓

┌─────────────────────────────────────────────────────────┐
│                   NEW SETUP                             │
├─────────────────────────────────────────────────────────┤
│ Data Source:    DuckDB (TPC-H SF1) ← CHANGED           │
│ Vector Store:   PgVector (knowledge + learnings)       │
│ Agent Metadata: PostgreSQL (sessions, runs)            │
└─────────────────────────────────────────────────────────┘
```

**Key Insight:** We keep PostgreSQL for vector storage and agent metadata, but query TPC-H data from DuckDB.

---

## TPC-H Schema Overview

TPC-H contains 8 tables representing a product ordering database:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   REGION     │────▶│   NATION     │     │   PART       │
│ (5 rows)     │     │ (25 rows)    │     │ (200K rows)  │
└──────────────┘     └──────────────┘     └──────────────┘
                            │                     │
                            ↓                     ↓
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  CUSTOMER    │────▶│   ORDERS     │     │  PARTSUPP    │
│ (150K rows)  │     │ (1.5M rows)  │     │ (800K rows)  │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                     │
       │                    ↓                     │
       │             ┌──────────────┐             │
       └────────────▶│  LINEITEM    │◀────────────┘
                     │ (6M rows)    │
                     └──────────────┘
                            │
                            ↓
                     ┌──────────────┐
                     │  SUPPLIER    │
                     │ (10K rows)   │
                     └──────────────┘
```

### Tables

1. **REGION** - Geographic regions (5 regions)
2. **NATION** - Countries (25 nations, linked to regions)
3. **SUPPLIER** - Parts suppliers (10,000 suppliers)
4. **PART** - Parts catalog (200,000 parts)
5. **PARTSUPP** - Part supplier relationships (800,000 records)
6. **CUSTOMER** - Customers (150,000 customers)
7. **ORDERS** - Customer orders (1.5M orders)
8. **LINEITEM** - Order line items (6M line items)

**Total Rows:** ~8.5 million rows
**TPC-H SF1 Size:** ~1GB uncompressed

---

## Implementation Plan

### Phase 1: Setup DuckDB with TPC-H Data

#### 1A. Generate TPC-H Data

```bash
# Install DuckDB CLI (if not already installed)
# macOS:
brew install duckdb

# Or download from: https://duckdb.org/docs/installation/

# Create TPC-H database
mkdir -p data
cd data

# Generate TPC-H SF1 data using DuckDB
duckdb tpch_sf1.db << 'EOF'
INSTALL tpch;
LOAD tpch;
CALL dbgen(sf=1);

-- Verify data
SELECT
  'region' as table_name, COUNT(*) as row_count FROM region
UNION ALL
SELECT 'nation', COUNT(*) FROM nation
UNION ALL
SELECT 'supplier', COUNT(*) FROM supplier
UNION ALL
SELECT 'part', COUNT(*) FROM part
UNION ALL
SELECT 'partsupp', COUNT(*) FROM partsupp
UNION ALL
SELECT 'customer', COUNT(*) FROM customer
UNION ALL
SELECT 'orders', COUNT(*) FROM orders
UNION ALL
SELECT 'lineitem', COUNT(*) FROM lineitem;
EOF
```

Expected output:
```
┌─────────────┬───────────┐
│ table_name  │ row_count │
├─────────────┼───────────┤
│ region      │         5 │
│ nation      │        25 │
│ supplier    │     10000 │
│ part        │    200000 │
│ partsupp    │    800000 │
│ customer    │    150000 │
│ orders      │   1500000 │
│ lineitem    │   6001215 │
└─────────────┴───────────┘
```

#### 1B. Alternative: Download Pre-generated Data

```bash
# Using DuckDB's built-in TPC-H generator is easiest
# But you can also download from official TPC-H tools:
# http://www.tpc.org/tpch/
```

---

### Phase 2: Modify Dash to Support DuckDB

#### 2A. Update Dependencies

Add DuckDB support to `requirements.txt`:

```txt
# Add these lines
duckdb>=0.10.0
duckdb-engine>=0.11.0  # SQLAlchemy adapter for DuckDB
```

#### 2B. Create DuckDB Connection Module

Create `db/duckdb_url.py`:

```python
"""
DuckDB URL Builder
==================

Build DuckDB connection URL for TPC-H data.
"""

from os import getenv
from pathlib import Path


def build_duckdb_url() -> str:
    """Build DuckDB URL for TPC-H data."""
    # Default to data/tpch_sf1.db
    db_path = getenv("DUCKDB_PATH", "data/tpch_sf1.db")

    # Convert to absolute path
    db_path = Path(db_path).resolve()

    # DuckDB SQLAlchemy URL format
    return f"duckdb:///{db_path}"


duckdb_url = build_duckdb_url()
```

#### 2C. Update Agent Configuration

Modify `dash/agents.py`:

```python
# BEFORE (line 29):
from db import db_url, get_postgres_db

# AFTER:
from db import db_url, get_postgres_db
from db.duckdb_url import duckdb_url  # Add this

# ...

# BEFORE (line 68-73):
base_tools: list = [
    SQLTools(db_url=db_url),  # ← Uses PostgreSQL
    save_validated_query,
    introspect_schema,
    MCPTools(...),
]

# AFTER:
base_tools: list = [
    SQLTools(db_url=duckdb_url),  # ← Now uses DuckDB
    save_validated_query,
    introspect_schema,  # Need to update this too
    MCPTools(...),
]

# Also update introspect_schema tool (line 66):
# BEFORE:
introspect_schema = create_introspect_schema_tool(db_url)

# AFTER:
introspect_schema = create_introspect_schema_tool(duckdb_url)
```

---

### Phase 3: Create TPC-H Knowledge Base

#### 3A. Table Metadata

Create `dash/knowledge/tables/` files:

**region.json:**
```json
{
  "table_name": "region",
  "table_description": "Geographic regions. Only 5 regions in total.",
  "use_cases": [
    "Regional analysis",
    "Geographic aggregations"
  ],
  "data_quality_notes": [
    "Only 5 regions: AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST",
    "r_regionkey is INTEGER primary key (0-4)"
  ],
  "table_columns": [
    {
      "name": "r_regionkey",
      "type": "INTEGER",
      "description": "Unique region identifier (0-4)"
    },
    {
      "name": "r_name",
      "type": "VARCHAR",
      "description": "Region name (e.g., 'AMERICA', 'ASIA')"
    },
    {
      "name": "r_comment",
      "type": "VARCHAR",
      "description": "Free-form comment about the region"
    }
  ]
}
```

**nation.json:**
```json
{
  "table_name": "nation",
  "table_description": "Countries/nations, linked to regions. 25 nations total.",
  "use_cases": [
    "National-level analysis",
    "Regional grouping",
    "Supplier/customer location"
  ],
  "data_quality_notes": [
    "25 nations total, evenly distributed across 5 regions",
    "n_nationkey is INTEGER primary key (0-24)",
    "n_regionkey references region(r_regionkey)"
  ],
  "table_columns": [
    {
      "name": "n_nationkey",
      "type": "INTEGER",
      "description": "Unique nation identifier (0-24)"
    },
    {
      "name": "n_name",
      "type": "VARCHAR",
      "description": "Nation name (e.g., 'UNITED STATES', 'CHINA')"
    },
    {
      "name": "n_regionkey",
      "type": "INTEGER",
      "description": "Foreign key to region table"
    },
    {
      "name": "n_comment",
      "type": "VARCHAR",
      "description": "Free-form comment"
    }
  ]
}
```

**customer.json:**
```json
{
  "table_name": "customer",
  "table_description": "Customer information. 150,000 customers at SF1.",
  "use_cases": [
    "Customer segmentation",
    "Market segment analysis",
    "Customer orders analysis"
  ],
  "data_quality_notes": [
    "c_acctbal can be negative (credit balance)",
    "c_mktsegment has 5 values: AUTOMOBILE, BUILDING, FURNITURE, MACHINERY, HOUSEHOLD",
    "c_nationkey references nation(n_nationkey)"
  ],
  "table_columns": [
    {
      "name": "c_custkey",
      "type": "INTEGER",
      "description": "Unique customer identifier"
    },
    {
      "name": "c_name",
      "type": "VARCHAR",
      "description": "Customer name (e.g., 'Customer#000000001')"
    },
    {
      "name": "c_address",
      "type": "VARCHAR",
      "description": "Customer address"
    },
    {
      "name": "c_nationkey",
      "type": "INTEGER",
      "description": "Foreign key to nation table"
    },
    {
      "name": "c_phone",
      "type": "VARCHAR",
      "description": "Phone number"
    },
    {
      "name": "c_acctbal",
      "type": "DECIMAL(15,2)",
      "description": "Account balance (can be negative)"
    },
    {
      "name": "c_mktsegment",
      "type": "VARCHAR",
      "description": "Market segment: AUTOMOBILE, BUILDING, FURNITURE, MACHINERY, HOUSEHOLD"
    },
    {
      "name": "c_comment",
      "type": "VARCHAR",
      "description": "Free-form comment"
    }
  ]
}
```

**orders.json:**
```json
{
  "table_name": "orders",
  "table_description": "Customer orders. 1.5M orders at SF1.",
  "use_cases": [
    "Order volume analysis",
    "Revenue reporting",
    "Order status tracking"
  ],
  "data_quality_notes": [
    "o_orderdate is DATE type",
    "o_orderstatus: 'O' (open), 'F' (filled), 'P' (partial)",
    "o_orderpriority: '1-URGENT', '2-HIGH', '3-MEDIUM', '4-NOT SPECIFIED', '5-LOW'",
    "o_totalprice is sum of lineitem prices for this order"
  ],
  "table_columns": [
    {
      "name": "o_orderkey",
      "type": "INTEGER",
      "description": "Unique order identifier"
    },
    {
      "name": "o_custkey",
      "type": "INTEGER",
      "description": "Foreign key to customer table"
    },
    {
      "name": "o_orderstatus",
      "type": "VARCHAR(1)",
      "description": "Order status: O (open), F (filled), P (partial)"
    },
    {
      "name": "o_totalprice",
      "type": "DECIMAL(15,2)",
      "description": "Total order price (sum of lineitems)"
    },
    {
      "name": "o_orderdate",
      "type": "DATE",
      "description": "Order date (YYYY-MM-DD)"
    },
    {
      "name": "o_orderpriority",
      "type": "VARCHAR",
      "description": "Priority: 1-URGENT, 2-HIGH, 3-MEDIUM, 4-NOT SPECIFIED, 5-LOW"
    },
    {
      "name": "o_clerk",
      "type": "VARCHAR",
      "description": "Clerk who processed the order"
    },
    {
      "name": "o_shippriority",
      "type": "INTEGER",
      "description": "Shipping priority (0-9)"
    },
    {
      "name": "o_comment",
      "type": "VARCHAR",
      "description": "Free-form comment"
    }
  ]
}
```

**lineitem.json:**
```json
{
  "table_name": "lineitem",
  "table_description": "Order line items. ~6M line items at SF1. Most important table for revenue analysis.",
  "use_cases": [
    "Detailed revenue analysis",
    "Part sales tracking",
    "Supplier performance",
    "Shipping analysis"
  ],
  "data_quality_notes": [
    "l_shipdate, l_commitdate, l_receiptdate are DATE types",
    "l_shipdate <= l_receiptdate always",
    "l_returnflag: 'R' (returned), 'A' (available), 'N' (not returned)",
    "l_linestatus: 'O' (open), 'F' (filled)",
    "Revenue = l_extendedprice * (1 - l_discount) * (1 + l_tax)"
  ],
  "table_columns": [
    {
      "name": "l_orderkey",
      "type": "INTEGER",
      "description": "Foreign key to orders table"
    },
    {
      "name": "l_partkey",
      "type": "INTEGER",
      "description": "Foreign key to part table"
    },
    {
      "name": "l_suppkey",
      "type": "INTEGER",
      "description": "Foreign key to supplier table"
    },
    {
      "name": "l_linenumber",
      "type": "INTEGER",
      "description": "Line number within order (1-7)"
    },
    {
      "name": "l_quantity",
      "type": "DECIMAL(15,2)",
      "description": "Quantity ordered"
    },
    {
      "name": "l_extendedprice",
      "type": "DECIMAL(15,2)",
      "description": "Extended price (quantity * unit price)"
    },
    {
      "name": "l_discount",
      "type": "DECIMAL(15,2)",
      "description": "Discount percentage (0.00 - 0.10)"
    },
    {
      "name": "l_tax",
      "type": "DECIMAL(15,2)",
      "description": "Tax percentage (0.00 - 0.08)"
    },
    {
      "name": "l_returnflag",
      "type": "VARCHAR(1)",
      "description": "Return status: R (returned), A (available), N (not returned)"
    },
    {
      "name": "l_linestatus",
      "type": "VARCHAR(1)",
      "description": "Line status: O (open), F (filled)"
    },
    {
      "name": "l_shipdate",
      "type": "DATE",
      "description": "Ship date"
    },
    {
      "name": "l_commitdate",
      "type": "DATE",
      "description": "Committed delivery date"
    },
    {
      "name": "l_receiptdate",
      "type": "DATE",
      "description": "Receipt date (>= l_shipdate)"
    },
    {
      "name": "l_shipinstruct",
      "type": "VARCHAR",
      "description": "Shipping instructions"
    },
    {
      "name": "l_shipmode",
      "type": "VARCHAR",
      "description": "Shipping mode: TRUCK, MAIL, SHIP, AIR, FOB, RAIL, REG AIR"
    },
    {
      "name": "l_comment",
      "type": "VARCHAR",
      "description": "Free-form comment"
    }
  ]
}
```

*(You'll also need: supplier.json, part.json, partsupp.json)*

#### 3B. Business Rules

Create `dash/knowledge/business/tpch_metrics.json`:

```json
{
  "metrics": [
    {
      "name": "Revenue",
      "definition": "l_extendedprice * (1 - l_discount) * (1 + l_tax) from lineitem",
      "calculation": "SUM(l_extendedprice * (1 - l_discount) * (1 + l_tax))"
    },
    {
      "name": "Net Revenue",
      "definition": "Revenue after discount, before tax",
      "calculation": "SUM(l_extendedprice * (1 - l_discount))"
    },
    {
      "name": "Average Discount",
      "definition": "Mean discount across line items",
      "calculation": "AVG(l_discount)"
    },
    {
      "name": "Order Count",
      "definition": "Number of distinct orders",
      "calculation": "COUNT(DISTINCT o_orderkey)"
    }
  ],
  "common_gotchas": [
    {
      "issue": "Revenue calculation",
      "solution": "Always use: l_extendedprice * (1 - l_discount) * (1 + l_tax)"
    },
    {
      "issue": "Date range queries",
      "solution": "Use >= and < for date ranges, e.g., o_orderdate >= '1995-01-01' AND o_orderdate < '1996-01-01'"
    },
    {
      "issue": "Market segments",
      "solution": "Only 5 valid values: AUTOMOBILE, BUILDING, FURNITURE, MACHINERY, HOUSEHOLD"
    },
    {
      "issue": "Order status",
      "solution": "o_orderstatus: 'O' (open), 'F' (filled), 'P' (partial) - single character"
    }
  ],
  "data_characteristics": [
    "TPC-H Scale Factor 1: ~1GB data",
    "Date range: 1992-01-01 to 1998-12-31 (7 years)",
    "Customers evenly distributed across 25 nations",
    "Orders follow realistic seasonal patterns"
  ]
}
```

#### 3C. Query Patterns

Create `dash/knowledge/queries/tpch_queries.sql`:

```sql
-- <query name>revenue_by_year</query name>
-- <query description>
-- Annual revenue from line items.
-- Uses standard TPC-H revenue calculation.
-- </query description>
-- <query>
SELECT
    EXTRACT(YEAR FROM l_shipdate) AS year,
    SUM(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS total_revenue
FROM lineitem
GROUP BY EXTRACT(YEAR FROM l_shipdate)
ORDER BY year
-- </query>


-- <query name>top_customers_by_revenue</query name>
-- <query description>
-- Top 10 customers by total revenue.
-- Joins orders and lineitems for accurate revenue.
-- </query description>
-- <query>
SELECT
    c.c_custkey,
    c.c_name,
    c.c_nationkey,
    SUM(l.l_extendedprice * (1 - l.l_discount)) AS total_revenue
FROM customer c
JOIN orders o ON c.c_custkey = o.o_custkey
JOIN lineitem l ON o.o_orderkey = l.l_orderkey
GROUP BY c.c_custkey, c.c_name, c.c_nationkey
ORDER BY total_revenue DESC
LIMIT 10
-- </query>


-- <query name>orders_by_market_segment</query name>
-- <query description>
-- Order count and revenue by market segment.
-- </query description>
-- <query>
SELECT
    c.c_mktsegment,
    COUNT(DISTINCT o.o_orderkey) AS order_count,
    SUM(o.o_totalprice) AS total_revenue
FROM customer c
JOIN orders o ON c.c_custkey = o.o_custkey
GROUP BY c.c_mktsegment
ORDER BY total_revenue DESC
-- </query>


-- <query name>supplier_performance</query name>
-- <query description>
-- Top suppliers by revenue and order volume.
-- </query description>
-- <query>
SELECT
    s.s_suppkey,
    s.s_name,
    n.n_name AS nation,
    COUNT(DISTINCT l.l_orderkey) AS order_count,
    SUM(l.l_extendedprice * (1 - l.l_discount)) AS total_revenue
FROM supplier s
JOIN nation n ON s.s_nationkey = n.n_nationkey
JOIN lineitem l ON s.s_suppkey = l.l_suppkey
GROUP BY s.s_suppkey, s.s_name, n.n_name
ORDER BY total_revenue DESC
LIMIT 20
-- </query>


-- <query name>regional_revenue</query name>
-- <query description>
-- Revenue by region through customer orders.
-- </query description>
-- <query>
SELECT
    r.r_name AS region,
    SUM(l.l_extendedprice * (1 - l.l_discount)) AS total_revenue
FROM region r
JOIN nation n ON r.r_regionkey = n.n_regionkey
JOIN customer c ON n.n_nationkey = c.c_nationkey
JOIN orders o ON c.c_custkey = o.o_custkey
JOIN lineitem l ON o.o_orderkey = l.l_orderkey
GROUP BY r.r_name
ORDER BY total_revenue DESC
-- </query>


-- <query name>shipping_mode_analysis</query name>
-- <query description>
-- Analysis by shipping mode: volume and revenue.
-- </query description>
-- <query>
SELECT
    l_shipmode,
    COUNT(*) AS shipment_count,
    SUM(l_quantity) AS total_quantity,
    SUM(l_extendedprice * (1 - l_discount)) AS total_revenue
FROM lineitem
GROUP BY l_shipmode
ORDER BY total_revenue DESC
-- </query>
```

---

### Phase 4: Update Docker Configuration

#### 4A. Mount DuckDB Volume

Update `compose.yaml`:

```yaml
services:
  dash-api:
    # ... existing config ...
    volumes:
      - .:/app
      - dash-data:/data
      - ./data:/app/data  # ← Add this line for DuckDB access
```

#### 4B. Update Environment Variables

Update `example.env`:

```bash
# Required
OPENAI_API_KEY=sk-***

# DuckDB Configuration
DUCKDB_PATH=/app/data/tpch_sf1.db

# PostgreSQL (for agent metadata and vector storage)
DB_HOST=dash-db
DB_PORT=5432
DB_USER=ai
DB_PASS=ai
DB_DATABASE=ai
```

---

### Phase 5: Load TPC-H Knowledge

```bash
# After generating TPC-H data and creating knowledge files:

# Build and start containers
docker compose up -d --build

# Load TPC-H knowledge base
docker exec -it dash-api python -m dash.scripts.load_knowledge

# Verify DuckDB connection
docker exec -it dash-api python -c "
import duckdb
conn = duckdb.connect('/app/data/tpch_sf1.db')
print(conn.execute('SELECT COUNT(*) FROM lineitem').fetchone())
"
```

---

## Updated Evaluation Plan

### Test Queries for TPC-H

#### Basic Queries
```
1. What is the total revenue in 1995?
2. How many customers are in each market segment?
3. Which region has the highest revenue?
4. What are the top 5 suppliers by revenue?
```

#### Aggregation
```
5. Show annual revenue trends from 1992 to 1998
6. Which customer has spent the most?
7. What is the average discount by shipping mode?
```

#### Complex Queries
```
8. Compare revenue across regions for the AUTOMOBILE segment
9. Which supplier in ASIA has the most orders?
10. Show monthly revenue for 1997 with year-over-year comparison
```

#### Learning Tests
```
11. Calculate revenue for order 12345
    → Should learn: revenue = l_extendedprice * (1 - l_discount) * (1 + l_tax)

12. Show orders with status 'F'
    → Should learn: o_orderstatus is single character

13. Find customers in the MACHINERY segment
    → Should learn: valid market segments
```

---

## TPC-H Official Queries

TPC-H comes with 22 standard queries. These are excellent for evaluation:

```bash
# Run TPC-H Q1: Pricing Summary Report
"Show pricing summary by return flag and line status for shipments before September 1998"

# Run TPC-H Q3: Shipping Priority Query
"Get the 10 unshipped orders with the highest value for BUILDING segment customers"

# Run TPC-H Q5: Local Supplier Volume Query
"Show revenue by nation for suppliers in ASIA region in 1994"

# Run TPC-H Q10: Returned Item Reporting Query
"List top 20 customers with returned items"
```

Full TPC-H query specifications: http://www.tpc.org/tpc_documents_current_versions/pdf/tpc-h_v3.0.1.pdf

---

## Expected Results

### Data Statistics (SF1)

```
region:      5 rows
nation:      25 rows
supplier:    10,000 rows
part:        200,000 rows
partsupp:    800,000 rows
customer:    150,000 rows
orders:      1,500,000 rows
lineitem:    ~6,000,000 rows
```

### Sample Queries & Expected Answers

**Q: What is the total revenue in 1995?**
```
Expected: ~$11.8 billion
(Actual value depends on exact data generation)
```

**Q: How many customers are in each market segment?**
```
Expected: ~30,000 per segment (evenly distributed)
AUTOMOBILE:  30,000
BUILDING:    30,000
FURNITURE:   30,000
HOUSEHOLD:   30,000
MACHINERY:   30,000
```

**Q: Which region has the highest revenue?**
```
Expected: AMERICA or ASIA (typically)
(Depends on data distribution)
```

---

## Advantages of TPC-H over F1 Dataset

| Aspect | F1 Dataset | TPC-H SF1 | Winner |
|--------|------------|-----------|--------|
| **Size** | ~5 tables, <100K rows | 8 tables, ~8.5M rows | TPC-H |
| **Complexity** | Simple schema | Realistic multi-table joins | TPC-H |
| **Standard** | Custom | Industry benchmark | TPC-H |
| **Known Queries** | Custom | 22 official queries | TPC-H |
| **Real-world** | Sports stats | Business transactions | TPC-H |
| **Data Quality Issues** | Artificial (position TEXT vs INT) | Realistic challenges | TPC-H |
| **Evaluation** | Custom tests | Comparable to benchmarks | TPC-H |

---

## Implementation Checklist

- [ ] Install DuckDB CLI
- [ ] Generate TPC-H SF1 data (`duckdb tpch_sf1.db`)
- [ ] Add `duckdb` and `duckdb-engine` to requirements.txt
- [ ] Create `db/duckdb_url.py`
- [ ] Update `dash/agents.py` (SQLTools, introspect_schema)
- [ ] Create 8 table metadata JSON files
- [ ] Create `tpch_metrics.json` business rules
- [ ] Create `tpch_queries.sql` patterns
- [ ] Update `compose.yaml` (mount data volume)
- [ ] Update `.env` (add DUCKDB_PATH)
- [ ] Test DuckDB connection
- [ ] Load knowledge base
- [ ] Run test queries
- [ ] Update evaluation test cases

---

## Next Steps

1. **Generate the data** (Phase 1)
2. **Implement code changes** (Phase 2)
3. **Create knowledge files** (Phase 3)
4. **Update Docker config** (Phase 4)
5. **Load and test** (Phase 5)
6. **Run TPC-H evaluation** (using official queries)

Would you like me to help implement any specific phase?
