#!/usr/bin/env python
"""
Enhanced TPC-H Evaluation for Dash
Compares Dash's SQL generation against actual TPC-H queries with result validation.
"""

import json
import time
import re
from datetime import datetime
from pathlib import Path
import duckdb
from dash.agents import dash

# TPC-H Queries with natural language prompts and golden SQL
TPCH_QUERIES = [
    {
        "id": "Q1",
        "name": "Pricing Summary Report",
        "question": "Show a pricing summary report of line items shipped before September 2, 1998, grouped by return flag and line status. Include quantity, extended price, discounts, taxes, averages, and counts.",
        "golden_sql": """
SELECT
    l_returnflag,
    l_linestatus,
    SUM(l_quantity) AS sum_qty,
    SUM(l_extendedprice) AS sum_base_price,
    SUM(l_extendedprice * (1 - l_discount)) AS sum_disc_price,
    SUM(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS sum_charge,
    AVG(l_quantity) AS avg_qty,
    AVG(l_extendedprice) AS avg_price,
    AVG(l_discount) AS avg_disc,
    COUNT(*) AS count_order
FROM lineitem
WHERE l_shipdate <= DATE '1998-12-01' - INTERVAL '90' DAY
GROUP BY l_returnflag, l_linestatus
ORDER BY l_returnflag, l_linestatus
        """,
        "category": "aggregation",
        "complexity": "medium",
    },
    {
        "id": "Q3",
        "name": "Shipping Priority",
        "question": "Get the 10 unshipped orders with the highest value for customers in the BUILDING market segment with orders placed before March 15, 1995. Show order key, revenue, order date, and ship priority.",
        "golden_sql": """
SELECT
    l_orderkey,
    SUM(l_extendedprice * (1 - l_discount)) AS revenue,
    o_orderdate,
    o_shippriority
FROM customer, orders, lineitem
WHERE c_mktsegment = 'BUILDING'
    AND c_custkey = o_custkey
    AND l_orderkey = o_orderkey
    AND o_orderdate < DATE '1995-03-15'
    AND l_shipdate > DATE '1995-03-15'
GROUP BY l_orderkey, o_orderdate, o_shippriority
ORDER BY revenue DESC, o_orderdate
LIMIT 10
        """,
        "category": "complex",
        "complexity": "medium",
    },
    {
        "id": "Q5",
        "name": "Local Supplier Volume",
        "question": "What is the revenue from line items supplied by suppliers from the ASIA region in 1994?",
        "golden_sql": """
SELECT
    n_name,
    SUM(l_extendedprice * (1 - l_discount)) AS revenue
FROM customer, orders, lineitem, supplier, nation, region
WHERE c_custkey = o_custkey
    AND l_orderkey = o_orderkey
    AND l_suppkey = s_suppkey
    AND c_nationkey = s_nationkey
    AND s_nationkey = n_nationkey
    AND n_regionkey = r_regionkey
    AND r_name = 'ASIA'
    AND o_orderdate >= DATE '1994-01-01'
    AND o_orderdate < DATE '1995-01-01'
GROUP BY n_name
ORDER BY revenue DESC
        """,
        "category": "complex",
        "complexity": "high",
    },
    {
        "id": "Q6",
        "name": "Forecasting Revenue Change",
        "question": "What is the potential revenue if discounts between 5% and 7% were eliminated for line items with quantity less than 24 shipped in 1994?",
        "golden_sql": """
SELECT
    SUM(l_extendedprice * l_discount) AS revenue
FROM lineitem
WHERE l_shipdate >= DATE '1994-01-01'
    AND l_shipdate < DATE '1995-01-01'
    AND l_discount BETWEEN 0.05 AND 0.07
    AND l_quantity < 24
        """,
        "category": "basic",
        "complexity": "low",
    },
    {
        "id": "Q10",
        "name": "Returned Item Reporting",
        "question": "List the top 20 customers by revenue who have returned items between October 1, 1993 and December 31, 1993. Include customer details and nation.",
        "golden_sql": """
SELECT
    c_custkey,
    c_name,
    SUM(l_extendedprice * (1 - l_discount)) AS revenue,
    c_acctbal,
    n_name,
    c_address,
    c_phone,
    c_comment
FROM customer, orders, lineitem, nation
WHERE c_custkey = o_custkey
    AND l_orderkey = o_orderkey
    AND o_orderdate >= DATE '1993-10-01'
    AND o_orderdate < DATE '1994-01-01'
    AND l_returnflag = 'R'
    AND c_nationkey = n_nationkey
GROUP BY c_custkey, c_name, c_acctbal, c_phone, n_name, c_address, c_comment
ORDER BY revenue DESC
LIMIT 20
        """,
        "category": "complex",
        "complexity": "medium",
    },
    {
        "id": "Q12",
        "name": "Shipping Modes and Order Priority",
        "question": "Count high and low priority orders by shipping mode for MAIL and SHIP shipments received in 1994.",
        "golden_sql": """
SELECT
    l_shipmode,
    SUM(CASE WHEN o_orderpriority = '1-URGENT' OR o_orderpriority = '2-HIGH'
        THEN 1 ELSE 0 END) AS high_line_count,
    SUM(CASE WHEN o_orderpriority <> '1-URGENT' AND o_orderpriority <> '2-HIGH'
        THEN 1 ELSE 0 END) AS low_line_count
FROM orders, lineitem
WHERE o_orderkey = l_orderkey
    AND l_shipmode IN ('MAIL', 'SHIP')
    AND l_commitdate < l_receiptdate
    AND l_shipdate < l_commitdate
    AND l_receiptdate >= DATE '1994-01-01'
    AND l_receiptdate < DATE '1995-01-01'
GROUP BY l_shipmode
ORDER BY l_shipmode
        """,
        "category": "aggregation",
        "complexity": "medium",
    },
    {
        "id": "Q14",
        "name": "Promotion Effect",
        "question": "What percentage of revenue in September 1994 came from promotional parts (parts with type starting with 'PROMO')?",
        "golden_sql": """
SELECT
    100.00 * SUM(CASE WHEN p_type LIKE 'PROMO%'
        THEN l_extendedprice * (1 - l_discount)
        ELSE 0 END) / SUM(l_extendedprice * (1 - l_discount)) AS promo_revenue
FROM lineitem, part
WHERE l_partkey = p_partkey
    AND l_shipdate >= DATE '1994-09-01'
    AND l_shipdate < DATE '1994-10-01'
        """,
        "category": "aggregation",
        "complexity": "medium",
    },
]


def extract_sql_from_response(response_content):
    """Extract SQL from agent response."""
    # Look for SQL code blocks
    sql_pattern = r'```sql\n(.*?)\n```'
    matches = re.findall(sql_pattern, response_content, re.DOTALL)
    if matches:
        return matches[0].strip()

    # Look for SQL without code blocks (common patterns)
    select_pattern = r'(SELECT[\s\S]*?(?:;|$))'
    matches = re.findall(select_pattern, response_content, re.IGNORECASE)
    if matches:
        # Take the first complete SELECT statement
        return matches[0].strip().rstrip(';')

    return None


def execute_sql(sql, db_path):
    """Execute SQL against DuckDB and return results."""
    try:
        conn = duckdb.connect(db_path, read_only=True)
        result = conn.execute(sql).fetchall()
        conn.close()
        return result, None
    except Exception as e:
        return None, str(e)


def compare_results(dash_results, golden_results):
    """Compare query results for similarity."""
    if dash_results is None or golden_results is None:
        return 0.0, "One or both queries failed"

    # Convert to sets for comparison (order-independent)
    dash_set = set(tuple(row) if isinstance(row, (list, tuple)) else (row,) for row in dash_results)
    golden_set = set(tuple(row) if isinstance(row, (list, tuple)) else (row,) for row in golden_results)

    if len(golden_set) == 0:
        return 0.0, "Golden query returned no results"

    # Calculate intersection
    matching = len(dash_set.intersection(golden_set))
    total = len(golden_set)

    similarity = matching / total if total > 0 else 0.0

    if similarity == 1.0:
        return 1.0, "Exact match"
    elif similarity > 0.8:
        return similarity, f"Good match: {matching}/{total} rows"
    elif similarity > 0.5:
        return similarity, f"Partial match: {matching}/{total} rows"
    else:
        return similarity, f"Poor match: {matching}/{total} rows"


def run_enhanced_evaluation():
    """Run enhanced TPC-H evaluation."""
    results = []
    start_time = datetime.now()
    db_path = '/app/data/tpch_sf1.db'

    print("=" * 80)
    print(f"ENHANCED TPC-H EVALUATION - Started at {start_time}")
    print("=" * 80)
    print()

    for i, query in enumerate(TPCH_QUERIES, 1):
        print(f"[{i}/{len(TPCH_QUERIES)}] {query['id']}: {query['name']}")
        print(f"Category: {query['category']}, Complexity: {query['complexity']}")
        print(f"Question: {query['question'][:100]}...")

        query_start = time.time()
        result = {
            "id": query['id'],
            "name": query['name'],
            "category": query['category'],
            "complexity": query['complexity'],
            "question": query['question'],
        }

        try:
            # 1. Run Dash agent
            print("  → Running Dash agent...")
            response = dash.run(query['question'], stream=False)
            agent_duration = time.time() - query_start

            # 2. Extract SQL from response
            print("  → Extracting SQL...")
            dash_sql = extract_sql_from_response(response.content)

            if not dash_sql:
                print("  ❌ Could not extract SQL from response")
                result.update({
                    "success": False,
                    "error": "No SQL found in response",
                    "duration": agent_duration,
                })
                results.append(result)
                print()
                continue

            print(f"  → Extracted SQL ({len(dash_sql)} chars)")

            # 3. Execute Dash's SQL
            print("  → Executing Dash SQL...")
            dash_results, dash_error = execute_sql(dash_sql, db_path)

            # 4. Execute golden SQL
            print("  → Executing golden SQL...")
            golden_results, golden_error = execute_sql(query['golden_sql'], db_path)

            # 5. Compare results
            if dash_error:
                print(f"  ❌ Dash SQL error: {dash_error}")
                result.update({
                    "success": False,
                    "error": f"SQL execution error: {dash_error}",
                    "dash_sql": dash_sql,
                    "duration": agent_duration,
                })
            elif golden_error:
                print(f"  ⚠️  Golden SQL error: {golden_error}")
                result.update({
                    "success": True,
                    "dash_sql": dash_sql,
                    "dash_result_count": len(dash_results) if dash_results else 0,
                    "golden_error": golden_error,
                    "duration": agent_duration,
                    "score": 0.5,  # Partial credit if dash works but golden fails
                })
            else:
                print("  → Comparing results...")
                similarity, comparison_msg = compare_results(dash_results, golden_results)

                result.update({
                    "success": True,
                    "dash_sql": dash_sql,
                    "dash_result_count": len(dash_results),
                    "golden_result_count": len(golden_results),
                    "similarity_score": similarity,
                    "comparison": comparison_msg,
                    "duration": agent_duration,
                    "score": similarity,
                })

                if similarity == 1.0:
                    print(f"  ✅ Perfect match! ({len(dash_results)} rows)")
                elif similarity > 0.8:
                    print(f"  ✅ Good match: {similarity:.1%} ({comparison_msg})")
                elif similarity > 0.5:
                    print(f"  ⚠️  Partial match: {similarity:.1%} ({comparison_msg})")
                else:
                    print(f"  ❌ Poor match: {similarity:.1%} ({comparison_msg})")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            result.update({
                "success": False,
                "error": str(e),
                "duration": time.time() - query_start,
            })

        results.append(result)
        print()

    # Summary
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    successful = [r for r in results if r.get('success', False)]
    scores = [r.get('score', 0) for r in successful]
    avg_score = sum(scores) / len(scores) if scores else 0
    avg_duration = sum(r.get('duration', 0) for r in results) / len(results) if results else 0

    perfect_matches = sum(1 for r in results if r.get('similarity_score', 0) == 1.0)
    good_matches = sum(1 for r in results if 0.8 <= r.get('similarity_score', 0) < 1.0)
    partial_matches = sum(1 for r in results if 0.5 <= r.get('similarity_score', 0) < 0.8)
    poor_matches = sum(1 for r in results if 0 < r.get('similarity_score', 0) < 0.5)

    print("=" * 80)
    print("ENHANCED EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total Queries: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(results) - len(successful)}")
    print(f"Success Rate: {len(successful)/len(results)*100:.1f}%")
    print(f"Average Similarity Score: {avg_score:.1%}")
    print(f"Average Duration: {avg_duration:.1f}s")
    print(f"Total Duration: {total_duration:.1f}s")
    print()
    print("Result Quality:")
    print(f"  Perfect Matches (100%):     {perfect_matches}")
    print(f"  Good Matches (80-99%):      {good_matches}")
    print(f"  Partial Matches (50-79%):   {partial_matches}")
    print(f"  Poor Matches (<50%):        {poor_matches}")
    print()

    # By category
    categories = set(r['category'] for r in results)
    for category in sorted(categories):
        cat_results = [r for r in results if r['category'] == category]
        cat_successful = [r for r in cat_results if r.get('success', False)]
        cat_scores = [r.get('score', 0) for r in cat_successful]
        cat_avg_score = sum(cat_scores) / len(cat_scores) if cat_scores else 0
        print(f"{category.upper()}: {len(cat_successful)}/{len(cat_results)} success, avg score: {cat_avg_score:.1%}")

    # Save results
    output_file = f"enhanced_tpch_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": start_time.isoformat(),
            "total_duration_seconds": total_duration,
            "summary": {
                "total": len(results),
                "successful": len(successful),
                "failed": len(results) - len(successful),
                "success_rate": len(successful)/len(results),
                "average_score": avg_score,
                "average_duration": avg_duration,
                "perfect_matches": perfect_matches,
                "good_matches": good_matches,
                "partial_matches": partial_matches,
                "poor_matches": poor_matches,
            },
            "results": results,
        }, f, indent=2)

    print()
    print(f"Results saved to: {output_file}")
    print("=" * 80)

    return results


if __name__ == "__main__":
    run_enhanced_evaluation()
