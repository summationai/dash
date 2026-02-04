#!/usr/bin/env python
"""
Final TPC-H Evaluation for Dash
Pre-computes golden results, then validates Dash's answers.
"""

import json
import time
from datetime import datetime
import duckdb
from dash.agents import dash
from tpch_queries_golden import TPCH_GOLDEN_QUERIES

DB_PATH = '/app/data/tpch_sf1.db'


def precompute_golden_results():
    """Execute all golden SQL queries upfront and cache results."""
    print("Precomputing golden results from TPC-H queries...")
    golden_cache = {}

    conn = duckdb.connect(DB_PATH, read_only=True)

    for query in TPCH_GOLDEN_QUERIES:
        try:
            result = conn.execute(query['golden_sql']).fetchall()
            golden_cache[query['id']] = {
                "success": True,
                "results": result,
                "row_count": len(result),
            }
            print(f"  ✓ {query['id']}: {len(result)} rows")
        except Exception as e:
            golden_cache[query['id']] = {
                "success": False,
                "error": str(e),
            }
            print(f"  ✗ {query['id']}: ERROR - {str(e)[:60]}")

    conn.close()
    print(f"\nCached {len([v for v in golden_cache.values() if v['success']])} golden results\n")
    return golden_cache


def format_value(v):
    """Format value for display and searching."""
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        if isinstance(v, float):
            # Format large numbers with commas
            if abs(v) >= 1000000:
                return f"${v/1000000:.2f}M" if v >= 0 else f"-${abs(v)/1000000:.2f}M"
            elif abs(v) >= 1000:
                return f"${v:,.2f}" if v >= 0 else f"-${abs(v):,.2f}"
            else:
                return f"{v:.2f}"
        else:
            return f"{v:,}" if abs(v) >= 1000 else str(v)
    return str(v)


def check_answer_correctness(response_content, golden_data):
    """Check if golden results are reflected in the response."""
    if not golden_data['success']:
        return 0.0, "Golden query failed", []

    results = golden_data['results']
    if not results:
        # Check if response mentions "no results" or "empty"
        if any(term in response_content.lower() for term in ['no results', 'empty', '0 rows', 'zero']):
            return 1.0, "Correctly identified empty result", []
        return 0.0, "Expected empty result not mentioned", []

    response_upper = response_content.upper()
    found_count = 0
    total_checks = 0

    # Strategy: Check if key values from first few rows appear
    for row_idx, row in enumerate(results[:5]):  # Check first 5 rows
        for col_idx, value in enumerate(row):
            if value is None:
                continue

            total_checks += 1

            # Check different representations
            if isinstance(value, (int, float)):
                # Format variations to check
                checks = [
                    str(int(value)) if isinstance(value, int) else f"{value:.2f}",
                    f"{value:,.0f}".replace(',', ''),  # Without commas
                    f"{value:.2f}".replace('.', ','),   # European format
                ]

                # For large numbers, also check abbreviated forms
                if abs(value) >= 1000000:
                    checks.append(f"{value/1000000:.1f}")  # Millions
                if abs(value) >= 1000000000:
                    checks.append(f"{value/1000000000:.1f}")  # Billions

                if any(check in response_upper for check in checks):
                    found_count += 1

            elif isinstance(value, str):
                if value.upper() in response_upper:
                    found_count += 1

    score = found_count / total_checks if total_checks > 0 else 0.5

    if score >= 0.7:
        return score, f"Excellent: {found_count}/{total_checks} values found", []
    elif score >= 0.4:
        return score, f"Good: {found_count}/{total_checks} values found", []
    elif score > 0:
        return score, f"Partial: {found_count}/{total_checks} values found", []
    else:
        return 0.0, f"No expected values found (0/{total_checks})", []


def run_final_evaluation(query_ids=None):
    """Run final TPC-H evaluation."""
    start_time = datetime.now()

    # Pre-compute all golden results
    golden_cache = precompute_golden_results()

    # Filter queries
    queries_to_run = TPCH_GOLDEN_QUERIES
    if query_ids:
        queries_to_run = [q for q in TPCH_GOLDEN_QUERIES if q['id'] in query_ids]

    print("=" * 80)
    print(f"FINAL TPC-H EVALUATION")
    print(f"Testing: {len(queries_to_run)} queries")
    print("=" * 80)
    print()

    results = []

    for i, query in enumerate(queries_to_run, 1):
        print(f"[{i}/{len(queries_to_run)}] {query['id']}: {query['name']}")

        if query['id'] not in golden_cache or not golden_cache[query['id']]['success']:
            print(f"  ⚠️  Skipping - golden query failed")
            results.append({
                "id": query['id'],
                "name": query['name'],
                "category": query['category'],
                "complexity": query['complexity'],
                "success": False,
                "error": "Golden query failed",
                "score": 0.0,
            })
            print()
            continue

        query_start = time.time()

        try:
            # Run Dash
            print(f"  → Asking Dash...")
            response = dash.run(query['question'], stream=False)
            duration = time.time() - query_start

            # Validate answer
            print(f"  → Validating answer...")
            score, validation_msg, _ = check_answer_correctness(
                response.content,
                golden_cache[query['id']]
            )

            result = {
                "id": query['id'],
                "name": query['name'],
                "category": query['category'],
                "complexity": query['complexity'],
                "success": True,
                "score": score,
                "validation": validation_msg,
                "duration": duration,
                "response_length": len(response.content),
                "golden_rows": golden_cache[query['id']]['row_count'],
            }

            if score >= 0.7:
                print(f"  ✅ Excellent: {score:.0%} - {validation_msg}")
            elif score >= 0.4:
                print(f"  ✅ Good: {score:.0%} - {validation_msg}")
            elif score > 0:
                print(f"  ⚠️  Partial: {score:.0%} - {validation_msg}")
            else:
                print(f"  ❌ Failed: {validation_msg}")

            print(f"  ⏱️  {duration:.1f}s")

        except Exception as e:
            result = {
                "id": query['id'],
                "name": query['name'],
                "category": query['category'],
                "complexity": query['complexity'],
                "success": False,
                "error": str(e)[:200],
                "score": 0.0,
                "duration": time.time() - query_start,
            }
            print(f"  ❌ Error: {str(e)[:80]}")

        results.append(result)
        print()

    # Summary
    total_duration = (datetime.now() - start_time).total_seconds()
    scores = [r.get('score', 0) for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0

    excellent = sum(1 for s in scores if s >= 0.7)
    good = sum(1 for s in scores if 0.4 <= s < 0.7)
    partial = sum(1 for s in scores if 0 < s < 0.4)
    failed = sum(1 for s in scores if s == 0)

    print("=" * 80)
    print("FINAL EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Queries Tested:   {len(results)}")
    print(f"Average Score:    {avg_score:.1%}")
    print(f"Avg Duration:     {sum(r.get('duration', 0) for r in results) / len(results):.1f}s per query")
    print(f"Total Time:       {total_duration/60:.1f} minutes")
    print()
    print("Answer Correctness:")
    print(f"  ✅ Excellent (≥70%):    {excellent:2d} / {len(results)}")
    print(f"  ✅ Good (40-69%):       {good:2d} / {len(results)}")
    print(f"  ⚠️  Partial (<40%):     {partial:2d} / {len(results)}")
    print(f"  ❌ Failed (0%):         {failed:2d} / {len(results)}")
    print()

    # By complexity
    for complexity in ['low', 'medium', 'high']:
        comp_results = [r for r in results if r.get('complexity') == complexity]
        if comp_results:
            comp_scores = [r.get('score', 0) for r in comp_results]
            comp_avg = sum(comp_scores) / len(comp_scores)
            comp_excellent = sum(1 for s in comp_scores if s >= 0.7)
            print(f"  {complexity.upper():8s}: {comp_excellent:2d}/{len(comp_results):2d} excellent, avg: {comp_avg:.1%}")

    # Save
    output_file = f"final_tpch_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": start_time.isoformat(),
            "total_duration_seconds": total_duration,
            "summary": {
                "total": len(results),
                "average_score": avg_score,
                "excellent": excellent,
                "good": good,
                "partial": partial,
                "failed": failed,
            },
            "results": results,
        }, f, indent=2)

    print(f"\n📁 Results: {output_file}")
    print("=" * 80)

    return results


if __name__ == "__main__":
    import sys
    query_ids = sys.argv[1:] if len(sys.argv) > 1 else None
    run_final_evaluation(query_ids=query_ids)
