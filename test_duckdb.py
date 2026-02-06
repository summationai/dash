#!/usr/bin/env python
"""Test DuckDB connection to TPC-H data."""

from db.duckdb_url import duckdb_url
import duckdb

print(f'DuckDB URL: {duckdb_url}')

conn = duckdb.connect('/app/data/tpch_sf1.db', read_only=True)
print('\nTPC-H Table Counts:')
result = conn.execute('''
  SELECT 'region' as table_name, COUNT(*) as row_count FROM region
  UNION ALL SELECT 'nation', COUNT(*) FROM nation
  UNION ALL SELECT 'supplier', COUNT(*) FROM supplier
  UNION ALL SELECT 'part', COUNT(*) FROM part
  UNION ALL SELECT 'partsupp', COUNT(*) FROM partsupp
  UNION ALL SELECT 'customer', COUNT(*) FROM customer
  UNION ALL SELECT 'orders', COUNT(*) FROM orders
  UNION ALL SELECT 'lineitem', COUNT(*) FROM lineitem
''').fetchall()
for row in result:
    print(f'  {row[0]:12} {row[1]:>10,}')
conn.close()
print('\n✅ DuckDB connection successful!')
