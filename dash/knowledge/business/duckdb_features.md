# DuckDB SQL Query Syntax and Performance Guide 

## General Knowledge

### Basic Syntax and Features

**Identifiers and Literals:**
- Use double quotes (`"`) for identifiers with spaces/special characters or case-sensitivity
- Use single quotes (`'`) for string literals

**Flexible Query Structure:**
- Queries can start with `FROM`: `FROM my_table WHERE condition;` (equivalent to `SELECT * FROM my_table WHERE condition;`)
- `SELECT` without `FROM` for expressions: `SELECT 1 + 1 AS result;`
- Support for `CREATE TABLE AS` (CTAS): `CREATE TABLE new_table AS SELECT * FROM old_table;`

**Advanced Column Selection:**
- Exclude columns: `SELECT * EXCLUDE (sensitive_data) FROM users;`
- Replace columns: `SELECT * REPLACE (UPPER(name) AS name) FROM users;`
- Pattern matching: `SELECT COLUMNS('sales_.*') FROM sales_data;`
- Transform multiple columns: `SELECT AVG(COLUMNS('sales_.*')) FROM sales_data;`

**Grouping and Ordering Shortcuts:**
- Group by all non-aggregated columns: `SELECT category, SUM(sales) FROM sales_data GROUP BY ALL;`
- Order by all columns: `SELECT * FROM my_table ORDER BY ALL;`

**Union Operations:**
- Union by column names: `SELECT * FROM table1 UNION BY NAME SELECT * FROM table2;`

**Complex Data Types:**
- Lists: `SELECT [1, 2, 3] AS my_list;`
- Structs: `SELECT {'a': 1, 'b': 'text'} AS my_struct;`
- Maps: `SELECT MAP([1,2],['one','two']) AS my_map;`
- Arrays (fixed size): `INTEGER[3]` vs Lists (variable size): `INTEGER[]`
- Access struct fields: `struct_col.field_name` or `struct_col['field_name']`
- Access map values: `map_col[key]`

**String and List Operations:**
- Slicing (1-indexed): `'DuckDB'[1:4]` or `[1, 2, 3, 4][1:3]`
- Function chaining: `'DuckDB'.replace('Duck', 'Goose').upper()`
- List comprehensions: `SELECT [x*2 FOR x IN [1, 2, 3]];`

**JSON Support:**
- JSON path expressions: `data->'$.user.id'` (returns JSON) or `data->>'$.event_type'` (returns text)

**Date/Time Operations:**
- String to timestamp: `strptime('2023-07-23', '%Y-%m-%d')::TIMESTAMP`
- Format timestamp: `strftime(NOW(), '%Y-%m-%d')`
- Extract parts: `EXTRACT(YEAR FROM DATE '2023-07-23')`

**Type Conversion:**
- Implicit conversions: `SELECT '42' + 1;` (returns 43)
- Explicit casting: `SELECT '42'::INTEGER + 1;`

**Column Aliases:**
- Can use aliases in WHERE/GROUP BY/HAVING: `SELECT a + b AS total FROM my_table WHERE total > 10;`

## Pivot/Unpivot

### When to Use Pivot/Unpivot

**PIVOT** transforms rows into columns - use when you need to:
- Convert categorical data into separate columns for analysis
- Create summary tables with categories as column headers
- Transform time series data to have time periods as columns

**UNPIVOT** transforms columns into rows - use when you need to:
- Normalize wide tables into long format
- Stack multiple measurement columns into name-value pairs
- Prepare data for time series analysis or visualization

### PIVOT Examples

**Basic Pivot - Sales by Year:**
```sql
-- Input: sales data with year column
-- Output: separate column for each year
PIVOT sales_data
ON year
USING sum(amount)
GROUP BY product;
```

**Multiple Value Columns:**
```sql
-- Calculate both sum and count for each year
PIVOT sales_data
ON year
USING sum(amount) AS total, count(*) AS transactions
GROUP BY product;
```

**Multiple Pivot Columns:**
```sql
-- Pivot by both country and year
PIVOT sales_data
ON country, year
USING sum(amount);
-- Creates columns like: US_2020, US_2021, NL_2020, NL_2021
```

### UNPIVOT Examples

**Basic Unpivot - Monthly Data to Long Format:**
```sql
-- Input: table with Jan, Feb, Mar columns
-- Output: month name and value columns
UNPIVOT monthly_sales
ON jan, feb, mar, apr, may, jun
INTO
    NAME month
    VALUE sales;
```

**Dynamic Unpivot with Column Expressions:**
```sql
-- Automatically unpivot all columns except ID columns
UNPIVOT monthly_sales
ON COLUMNS(* EXCLUDE (empid, dept))
INTO
    NAME month
    VALUE sales;
```

**Multiple Value Columns:**
```sql
-- Unpivot quarters with multiple metrics per quarter
UNPIVOT quarterly_data
ON (q1_sales, q1_units) AS q1, (q2_sales, q2_units) AS q2
INTO
    NAME quarter
    VALUE sales, units;
```

## Grouping Sets/Rollup/Cube

### When to Use Grouping Sets

Use **GROUPING SETS**, **ROLLUP**, and **CUBE** when you need multiple levels of aggregation in a single query:
- Creating subtotals and grand totals
- Generating reports with different granularities
- OLAP-style analysis with hierarchical dimensions

### GROUPING SETS

**Manual Grouping Sets:**
```sql
-- Generate aggregates for multiple grouping combinations
SELECT region, product, SUM(sales)
FROM sales_data
GROUP BY GROUPING SETS (
    (region, product),  -- By region and product
    (region),           -- By region only
    (product),          -- By product only
    ()                  -- Grand total
);
```

**ROLLUP - Hierarchical Totals:**
```sql
-- Creates hierarchical subtotals: (country, city), (country), ()
SELECT country, city, SUM(population)
FROM cities
GROUP BY ROLLUP (country, city);
```

**CUBE - All Combinations:**
```sql
-- Creates all possible combinations: (a,b,c), (a,b), (a,c), (b,c), (a), (b), (c), ()
SELECT region, product, channel, SUM(sales)
FROM sales_data
GROUP BY CUBE (region, product, channel);
```

### Identifying Groups with GROUPING_ID()

```sql
SELECT 
    region, 
    product, 
    SUM(sales),
    GROUPING_ID(region, product) AS grouping_level
FROM sales_data
GROUP BY CUBE (region, product);

-- grouping_level values:
-- 0: both region and product (detail level)
-- 1: region only (product rolled up)
-- 2: product only (region rolled up) 
-- 3: grand total (both rolled up)
```

## Performance Tips

### Join Optimization

**Prefer Efficient Join Types:**
- Start with inner joins to reduce dataset size early
- Be cautious with semi-joins on large datasets (may cause nested loop joins)
- Consider rewriting semi-joins as `IN` statements if performance issues occur

**Join Order:**
- Use inner joins early in complex queries to cull rows
- Filter data before joins when possible
- Consider breaking complex joins into temporary tables if needed

### Predicate Pushdown

**Enable Filter Pushdown:**
```sql
-- Good: Allows predicate pushdown
WHERE timestamp >= '2023-01-01'

-- Bad: Prevents pushdown (avoid functions on left side)
WHERE timestamp::DATE >= '2023-01-01'
```

### Window Functions and Aggregations

**Efficient Aggregation Patterns:**
- Use `arg_max()` and `arg_min()` instead of complex window functions for "most recent" queries
- Remember window functions are pipeline breakers (materialize results)
- Use `QUALIFY` instead of `WHERE` for filtering window function results

### QUALIFY Clause

The `QUALIFY` clause is specifically designed to filter results based on window functions, similar to how `HAVING` filters aggregate functions. It eliminates the need for subqueries or CTEs when filtering on window function results.

**When to Use QUALIFY:**
- Filter rows based on rankings (ROW_NUMBER, RANK, DENSE_RANK)
- Get top N records per group
- Filter based on running totals or moving averages
- Remove duplicates while keeping specific rows per group

**Basic QUALIFY Examples:**

```sql
-- Get top 2 products by sales in each category
SELECT category, product_name, sales_amount
FROM products
QUALIFY ROW_NUMBER() OVER (PARTITION BY category ORDER BY sales_amount DESC) <= 2;
```

```sql
-- Get most recent record per customer
SELECT customer_id, order_date, order_total
FROM orders
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) = 1;
```

**QUALIFY vs Alternatives:**

```sql
-- Using QUALIFY (preferred)
SELECT employee_id, salary, department
FROM employees
QUALIFY RANK() OVER (PARTITION BY department ORDER BY salary DESC) <= 3;

-- Without QUALIFY (requires subquery)
SELECT employee_id, salary, department
FROM (
    SELECT employee_id, salary, department,
           RANK() OVER (PARTITION BY department ORDER BY salary DESC) as salary_rank
    FROM employees
) ranked
WHERE salary_rank <= 3;
```

**Advanced QUALIFY Usage:**

```sql
-- Filter based on multiple window functions
SELECT product_id, sales_date, daily_sales
FROM sales
QUALIFY 
    ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY sales_date DESC) <= 7  -- Last 7 days
    AND daily_sales > AVG(daily_sales) OVER (PARTITION BY product_id);        -- Above average

-- Using window function aliases
SELECT customer_id, purchase_date, amount,
       ROW_NUMBER() OVER w as recency_rank
FROM purchases
WINDOW w AS (PARTITION BY customer_id ORDER BY purchase_date DESC)
QUALIFY recency_rank = 1;
```

### Query Structure Best Practices

- Avoid unnecessary `ORDER BY` on intermediate results
- Filter early to reduce data volume before blocking operations
- Use CTEs to break complex queries into manageable parts
- Use CTEs instead of repeated subqueries (DuckDB can auto-materialize identical CTEs)

**Avoid These Patterns:**
- Correlated subqueries (use rarely)
- Cross products and cartesian joins
- Unnecessary sorting of large intermediate results
- Functions on the left side of WHERE clauses (prevents pushdown)