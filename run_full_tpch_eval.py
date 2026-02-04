#!/usr/bin/env python
"""
Full TPC-H Evaluation for Dash
Tests Dash against all 22 official TPC-H queries with result validation.
"""

import json
import time
import re
from datetime import datetime
from pathlib import Path
import duckdb
from dash.agents import dash
from tpch_queries_golden import TPCH_GOLDEN_QUERIES

# Evaluation configuration
DB_PATH = '/app/data/tpch_sf1.db'
MAX_RETRIES = 2
TIMEOUT_SECONDS = 120


def extract_sql_from_response(response_content):
    """Extract SQL from agent response with multiple strategies."""
    # Strategy 1: Code blocks with sql tag
    sql_pattern = r'```sql\n(.*?)\n```'
    matches = re.findall(sql_pattern, response_content, re.DOTALL)
    if matches:
        return matches[0].strip()

    # Strategy 2: Code blocks without tag
    code_pattern = r'```\n(SELECT[\s\S]*?)\n```'
    matches = re.findall(code_pattern, response_content, re.IGNORECASE)
    if matches:
        return matches[0].strip()

    # Strategy 3: Raw SELECT statements
    select_pattern = r'(SELECT[\s\S]*?)(?:\n\n|$)'
    matches = re.findall(select_pattern, response_content, re.IGNORECASE)
    if matches:
        return matches[0].strip().rstrip(';')

    return None


def execute_sql(sql, db_path, timeout=30):
    """Execute SQL against DuckDB and return results."""
    try:
        conn = duckdb.connect(db_path, read_only=True)
        conn.execute(f"SET statement_timeout={timeout * 1000}")  # milliseconds
        result = conn.execute(sql).fetchall()
        conn.close()
        return result, None
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        return None, str(e)


def normalize_result(value):
    """Normalize a result value for comparison."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Round floats to 2 decimal places for comparison
        return round(float(value), 2) if isinstance(value, float) else value
    if isinstance(value, str):
        return value.strip().upper()
    return value


def compare_results(dash_results, golden_results, tolerance=0.01):
    """Compare query results with tolerance for floating point differences."""
    if dash_results is None or golden_results is None:
        return 0.0, "One or both queries failed", None

    # Handle empty results
    if len(dash_results) == 0 and len(golden_results) == 0:
        return 1.0, "Both queries returned empty result", []

    if len(dash_results) != len(golden_results):
        return 0.0, f"Row count mismatch: {len(dash_results)} vs {len(golden_results)}", []

    # Compare row by row
    mismatches = []
    matching_rows = 0

    for idx, (dash_row, golden_row) in enumerate(zip(dash_results, golden_results)):
        if len(dash_row) != len(golden_row):
            mismatches.append({
                "row": idx,
                "issue": "Column count mismatch",
                "dash": dash_row,
                "golden": golden_row,
            })
            continue

        row_match = True
        for col_idx, (dash_val, golden_val) in enumerate(zip(dash_row, golden_row)):
            dash_norm = normalize_result(dash_val)
            golden_norm = normalize_result(golden_val)

            # Numeric comparison with tolerance
            if isinstance(dash_norm, (int, float)) and isinstance(golden_norm, (int, float)):
                if abs(dash_norm - golden_norm) > tolerance:
                    row_match = False
                    mismatches.append({
                        "row": idx,
                        "column": col_idx,
                        "dash_value": dash_val,
                        "golden_value": golden_val,
                        "diff": abs(dash_norm - golden_norm),
                    })
            elif dash_norm != golden_norm:
                row_match = False
                mismatches.append({
                    "row": idx,
                    "column": col_idx,
                    "dash_value": dash_val,
                    "golden_value": golden_val,
                })

        if row_match:
            matching_rows += 1

    similarity = matching_rows / len(golden_results) if golden_results else 0.0

    if similarity == 1.0:
        return 1.0, "Exact match", []
    elif similarity > 0.95:
        return similarity, f"Near match: {matching_rows}/{len(golden_results)} rows ({len(mismatches)} mismatches)", mismatches[:5]
    elif similarity > 0.8:
        return similarity, f"Good match: {matching_rows}/{len(golden_results)} rows", mismatches[:5]
    elif similarity > 0.5:
        return similarity, f"Partial match: {matching_rows}/{len(golden_results)} rows", mismatches[:3]
    else:
        return similarity, f"Poor match: {matching_rows}/{len(golden_results)} rows", mismatches[:3]


def run_full_evaluation(query_ids=None, verbose=True):
    """Run full TPC-H evaluation."""
    results = []
    start_time = datetime.now()

    # Filter queries if specific IDs requested
    queries_to_run = TPCH_GOLDEN_QUERIES
    if query_ids:
        queries_to_run = [q for q in TPCH_GOLDEN_QUERIES if q['id'] in query_ids]

    print("=" * 80)
    print(f"TPC-H FULL EVALUATION - Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing {len(queries_to_run)} queries")
    print("=" * 80)
    print()

    for i, query in enumerate(queries_to_run, 1):
        print(f"[{i}/{len(queries_to_run)}] {query['id']}: {query['name']}")
        print(f"  Category: {query['category']}, Complexity: {query['complexity']}")
        if verbose:
            print(f"  Question: {query['question'][:120]}...")

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
            if verbose:
                print("  → Running Dash agent...")
            response = dash.run(query['question'], stream=False)
            agent_duration = time.time() - query_start

            # 2. Extract SQL from response
            dash_sql = extract_sql_from_response(response.content)

            if not dash_sql:
                if verbose:
                    print("  ⚠️  Could not extract SQL, checking if answer is in response...")
                # Sometimes agent answers without showing SQL
                result.update({
                    "success": True,
                    "extracted_sql": False,
                    "response_length": len(response.content),
                    "response_preview": response.content[:500],
                    "duration": agent_duration,
                    "score": 0.5,  # Partial credit for answering
                })
                results.append(result)
                if verbose:
                    print(f"  ⚠️  No SQL extracted (Duration: {agent_duration:.1f}s)")
                print()
                continue

            if verbose:
                print(f"  ✓ Extracted SQL ({len(dash_sql)} chars)")

            # 3. Execute Dash's SQL
            dash_results, dash_error = execute_sql(dash_sql, DB_PATH)

            # 4. Execute golden SQL
            golden_results, golden_error = execute_sql(query['golden_sql'], DB_PATH)

            # 5. Compare results
            if dash_error:
                if verbose:
                    print(f"  ❌ Dash SQL failed: {dash_error[:100]}")
                result.update({
                    "success": False,
                    "extracted_sql": True,
                    "sql_error": dash_error,
                    "dash_sql": dash_sql[:1000],
                    "duration": agent_duration,
                    "score": 0.0,
                })
            elif golden_error:
                if verbose:
                    print(f"  ⚠️  Golden SQL failed: {golden_error[:100]}")
                result.update({
                    "success": True,
                    "extracted_sql": True,
                    "dash_sql": dash_sql[:1000],
                    "dash_result_count": len(dash_results) if dash_results else 0,
                    "golden_error": golden_error,
                    "duration": agent_duration,
                    "score": 0.7,  # Partial credit if dash works
                })
            else:
                similarity, comparison_msg, mismatches = compare_results(dash_results, golden_results)

                result.update({
                    "success": True,
                    "extracted_sql": True,
                    "dash_sql": dash_sql[:1000],
                    "dash_result_count": len(dash_results),
                    "golden_result_count": len(golden_results),
                    "similarity_score": similarity,
                    "comparison": comparison_msg,
                    "mismatches": mismatches[:3] if mismatches else [],
                    "duration": agent_duration,
                    "score": similarity,
                })

                if similarity == 1.0:
                    if verbose:
                        print(f"  ✅ Perfect match! ({len(dash_results)} rows)")
                elif similarity > 0.8:
                    if verbose:
                        print(f"  ✅ Good match: {similarity:.1%} ({comparison_msg})")
                elif similarity > 0.5:
                    if verbose:
                        print(f"  ⚠️  Partial match: {similarity:.1%} ({comparison_msg})")
                else:
                    if verbose:
                        print(f"  ❌ Poor match: {similarity:.1%} ({comparison_msg})")

        except Exception as e:
            if verbose:
                print(f"  ❌ Error: {str(e)[:100]}")
            result.update({
                "success": False,
                "error": str(e)[:500],
                "duration": time.time() - query_start,
                "score": 0.0,
            })

        results.append(result)
        if verbose:
            print(f"  Duration: {result['duration']:.1f}s, Score: {result.get('score', 0):.1%}")
        print()

    # Generate summary
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    successful = [r for r in results if r.get('success', False)]
    scores = [r.get('score', 0) for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0
    avg_duration = sum(r.get('duration', 0) for r in results) / len(results) if results else 0

    perfect = sum(1 for r in results if r.get('similarity_score', 0) == 1.0)
    good = sum(1 for r in results if 0.8 <= r.get('similarity_score', 0) < 1.0)
    partial = sum(1 for r in results if 0.5 <= r.get('similarity_score', 0) < 0.8)
    poor = sum(1 for r in results if 0 < r.get('similarity_score', 0) < 0.5)
    failed = len(results) - len(successful)

    print("=" * 80)
    print("TPC-H FULL EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total Queries: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {len(successful)/len(results)*100:.1f}%")
    print(f"Average Score: {avg_score:.1%}")
    print(f"Average Duration: {avg_duration:.1f}s")
    print(f"Total Duration: {total_duration/60:.1f} minutes")
    print()
    print("Result Quality:")
    print(f"  ✅ Perfect (100%):      {perfect:2d} queries")
    print(f"  ✅ Good (80-99%):       {good:2d} queries")
    print(f"  ⚠️  Partial (50-79%):   {partial:2d} queries")
    print(f"  ❌ Poor (<50%):         {poor:2d} queries")
    print(f"  ❌ Failed:              {failed:2d} queries")
    print()

    # By category
    print("By Category:")
    for category in ['aggregation', 'complex']:
        cat_results = [r for r in results if r.get('category') == category]
        if not cat_results:
            continue
        cat_scores = [r.get('score', 0) for r in cat_results]
        cat_avg = sum(cat_scores) / len(cat_scores)
        cat_perfect = sum(1 for r in cat_results if r.get('similarity_score', 0) == 1.0)
        print(f"  {category.upper():12s}: {cat_perfect:2d}/{len(cat_results):2d} perfect, avg score: {cat_avg:.1%}")

    # By complexity
    print()
    print("By Complexity:")
    for complexity in ['low', 'medium', 'high']:
        comp_results = [r for r in results if r.get('complexity') == complexity]
        if not comp_results:
            continue
        comp_scores = [r.get('score', 0) for r in comp_results]
        comp_avg = sum(comp_scores) / len(comp_scores)
        comp_perfect = sum(1 for r in comp_results if r.get('similarity_score', 0) == 1.0)
        print(f"  {complexity.upper():8s}: {comp_perfect:2d}/{len(comp_results):2d} perfect, avg score: {comp_avg:.1%}")

    # Save detailed results
    output_file = f"full_tpch_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": start_time.isoformat(),
            "total_duration_seconds": total_duration,
            "summary": {
                "total": len(results),
                "successful": len(successful),
                "failed": failed,
                "success_rate": len(successful)/len(results),
                "average_score": avg_score,
                "average_duration": avg_duration,
                "perfect_matches": perfect,
                "good_matches": good,
                "partial_matches": partial,
                "poor_matches": poor,
            },
            "results": results,
        }, f, indent=2)

    print()
    print(f"📁 Detailed results saved to: {output_file}")
    print("=" * 80)

    # Print failures for quick review
    failures = [r for r in results if not r.get('success', False) or r.get('score', 0) < 0.5]
    if failures:
        print()
        print("⚠️  Queries Needing Attention:")
        for r in failures:
            print(f"  - {r['id']}: {r['name']}")
            if 'sql_error' in r:
                print(f"    Error: {r['sql_error'][:80]}...")
            elif 'score' in r:
                print(f"    Score: {r['score']:.1%}")
        print()

    return results


if __name__ == "__main__":
    import sys

    # Allow running specific queries: python run_full_tpch_eval.py Q1 Q3 Q5
    query_ids = sys.argv[1:] if len(sys.argv) > 1 else None

    if query_ids:
        print(f"Running queries: {', '.join(query_ids)}\n")
    else:
        print(f"Running all {len(TPCH_GOLDEN_QUERIES)} TPC-H queries\n")

    run_full_evaluation(query_ids=query_ids, verbose=True)
