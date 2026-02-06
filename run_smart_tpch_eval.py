#!/usr/bin/env python
"""
Smart TPC-H Evaluation for Dash
Validates answers by checking if golden SQL results appear in agent responses.
"""

import json
import time
import re
from datetime import datetime
import duckdb
from dash.agents import dash
from tpch_queries_golden import TPCH_GOLDEN_QUERIES

DB_PATH = '/app/data/tpch_sf1.db'


def execute_golden_sql(sql, db_path):
    """Execute golden SQL and return results."""
    try:
        conn = duckdb.connect(db_path, read_only=True)
        result = conn.execute(sql).fetchall()
        conn.close()
        return result, None
    except Exception as e:
        return None, str(e)


def check_answer_in_response(response_content, golden_results):
    """Check if golden results appear in the agent's response."""
    if not golden_results:
        return 0.0, "No golden results to compare", []

    found_values = []
    missing_values = []
    response_upper = response_content.upper()

    # Check for numeric values (with some tolerance)
    for row in golden_results[:10]:  # Check first 10 rows
        for value in row:
            if value is None:
                continue

            # Normalize value for searching
            if isinstance(value, (int, float)):
                # Try different formats
                search_terms = [
                    f"{value:,.0f}",  # 123,456
                    f"{value:.2f}",   # 123456.78
                    f"{int(value)}",  # 123456
                    f"${value:,.0f}", # $123,456
                ]

                value_found = any(term in response_upper or term.replace(',', '') in response_upper
                                 for term in search_terms)

                if value_found:
                    found_values.append(value)
                else:
                    missing_values.append(value)

            elif isinstance(value, str):
                # Search for string values
                if value.upper() in response_upper:
                    found_values.append(value)
                else:
                    missing_values.append(value)

    # Calculate score
    total_values = len(found_values) + len(missing_values)
    if total_values == 0:
        return 0.5, "No comparable values found", []

    score = len(found_values) / total_values

    if score >= 0.8:
        return score, f"Excellent: {len(found_values)}/{total_values} values found", found_values[:5]
    elif score >= 0.5:
        return score, f"Good: {len(found_values)}/{total_values} values found", found_values[:5]
    else:
        return score, f"Weak: {len(found_values)}/{total_values} values found", found_values[:5]


def run_smart_evaluation(query_ids=None, verbose=True):
    """Run smart TPC-H evaluation based on answer correctness."""
    results = []
    start_time = datetime.now()

    queries_to_run = TPCH_GOLDEN_QUERIES
    if query_ids:
        queries_to_run = [q for q in TPCH_GOLDEN_QUERIES if q['id'] in query_ids]

    print("=" * 80)
    print(f"SMART TPC-H EVALUATION - Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing {len(queries_to_run)} queries")
    print(f"Strategy: Validate answers appear in response (not SQL comparison)")
    print("=" * 80)
    print()

    for i, query in enumerate(queries_to_run, 1):
        print(f"[{i}/{len(queries_to_run)}] {query['id']}: {query['name']}")
        if verbose:
            print(f"  Category: {query['category']}, Complexity: {query['complexity']}")

        query_start = time.time()
        result = {
            "id": query['id'],
            "name": query['name'],
            "category": query['category'],
            "complexity": query['complexity'],
            "question": query['question'],
        }

        try:
            # 1. Execute golden SQL to get expected answer
            if verbose:
                print("  → Executing golden SQL...")
            golden_results, golden_error = execute_golden_sql(query['golden_sql'], DB_PATH)

            if golden_error:
                if verbose:
                    print(f"  ⚠️  Golden SQL error: {golden_error[:80]}")
                result.update({
                    "success": False,
                    "error": f"Golden SQL failed: {golden_error}",
                    "duration": time.time() - query_start,
                    "score": 0.0,
                })
                results.append(result)
                print()
                continue

            golden_row_count = len(golden_results) if golden_results else 0
            if verbose:
                print(f"  ✓ Golden query returned {golden_row_count} rows")

            # 2. Run Dash agent
            if verbose:
                print("  → Running Dash agent...")
            response = dash.run(query['question'], stream=False)
            agent_duration = time.time() - query_start

            if verbose:
                print(f"  ✓ Agent responded ({len(response.content)} chars)")

            # 3. Check if golden results appear in response
            if verbose:
                print("  → Validating answer correctness...")
            score, comparison_msg, found_values = check_answer_in_response(
                response.content, golden_results
            )

            result.update({
                "success": True,
                "response_length": len(response.content),
                "golden_result_count": golden_row_count,
                "score": score,
                "validation": comparison_msg,
                "sample_found_values": [str(v) for v in found_values[:5]],
                "duration": agent_duration,
                "response_preview": response.content[:300],
            })

            # Display result
            if score >= 0.8:
                if verbose:
                    print(f"  ✅ Excellent: {score:.1%} ({comparison_msg})")
            elif score >= 0.5:
                if verbose:
                    print(f"  ✅ Good: {score:.1%} ({comparison_msg})")
            else:
                if verbose:
                    print(f"  ⚠️  Weak: {score:.1%} ({comparison_msg})")

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
            print(f"  ⏱️  Duration: {result['duration']:.1f}s")
        print()

    # Summary
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    scores = [r.get('score', 0) for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0

    excellent = sum(1 for s in scores if s >= 0.8)
    good = sum(1 for s in scores if 0.5 <= s < 0.8)
    weak = sum(1 for s in scores if 0 < s < 0.5)
    failed = sum(1 for s in scores if s == 0)

    print("=" * 80)
    print("SMART EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total Queries: {len(results)}")
    print(f"Average Score: {avg_score:.1%}")
    print(f"Average Duration: {sum(r.get('duration', 0) for r in results) / len(results):.1f}s")
    print(f"Total Duration: {total_duration/60:.1f} minutes")
    print()
    print("Answer Quality:")
    print(f"  ✅ Excellent (≥80%):    {excellent:2d} queries")
    print(f"  ✅ Good (50-79%):       {good:2d} queries")
    print(f"  ⚠️  Weak (<50%):        {weak:2d} queries")
    print(f"  ❌ Failed (0%):         {failed:2d} queries")
    print()

    # By category
    print("By Category:")
    for category in sorted(set(r['category'] for r in results)):
        cat_results = [r for r in results if r.get('category') == category]
        cat_scores = [r.get('score', 0) for r in cat_results]
        cat_avg = sum(cat_scores) / len(cat_scores)
        cat_excellent = sum(1 for s in cat_scores if s >= 0.8)
        print(f"  {category.upper():12s}: {cat_excellent:2d}/{len(cat_results):2d} excellent, avg: {cat_avg:.1%}")

    # Save results
    output_file = f"smart_tpch_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": start_time.isoformat(),
            "evaluation_type": "smart_answer_validation",
            "total_duration_seconds": total_duration,
            "summary": {
                "total": len(results),
                "average_score": avg_score,
                "excellent": excellent,
                "good": good,
                "weak": weak,
                "failed": failed,
            },
            "results": results,
        }, f, indent=2)

    print(f"📁 Results saved to: {output_file}")
    print("=" * 80)

    return results


if __name__ == "__main__":
    import sys
    query_ids = sys.argv[1:] if len(sys.argv) > 1 else None

    if query_ids:
        print(f"Running queries: {', '.join(query_ids)}\n")

    run_smart_evaluation(query_ids=query_ids, verbose=True)
