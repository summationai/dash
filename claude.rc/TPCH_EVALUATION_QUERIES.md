# TPC-H Evaluation Queries

Natural language versions of the 22 standard TPC-H benchmark queries to evaluate Dash.

## Query 1: Pricing Summary Report
**Question:** "Show a summary report of pricing and discounts by return flag and line status for line items shipped before September 2, 1998. Include quantities, extended prices, discounts, taxes, averages, and counts."

**Tests:** Aggregation, date filtering, GROUP BY

---

## Query 2: Minimum Cost Supplier
**Question:** "Find suppliers who can supply part 123 at the minimum cost in the EUROPE region."

**Tests:** Subqueries, MIN aggregation, multi-table joins, region filtering

---

## Query 3: Shipping Priority
**Question:** "Get the 10 unshipped orders with the highest value for customers in the BUILDING market segment with orders placed before March 15, 1995."

**Tests:** Complex joins, ORDER BY with LIMIT, market segment filtering, date ranges

---

## Query 4: Order Priority Checking
**Question:** "How many orders have at least one line item received after the committed date, grouped by order priority? Only consider orders placed in Q2 1993."

**Tests:** EXISTS clause, date filtering, priority grouping

---

## Query 5: Local Supplier Volume
**Question:** "What is the revenue from line items supplied by suppliers from the ASIA region in 1994?"

**Tests:** Multi-table joins (5 tables), date filtering, revenue calculation, regional analysis

---

## Query 6: Forecasting Revenue Change
**Question:** "What is the potential revenue increase if discounts between 5% and 7% were eliminated for line items with quantity less than 24 shipped in 1994?"

**Tests:** BETWEEN clauses, discount analysis, quantity filtering, date ranges

---

## Query 7: Volume Shipping
**Question:** "Calculate the revenue volume between suppliers from nation X and customers from nation Y (and vice versa) for shipments in 1995 and 1996."

**Tests:** Bi-directional joins, CASE statements, year-based aggregation, nation filtering

---

## Query 8: National Market Share
**Question:** "What is the market share of a specific nation's suppliers for a specific part type in a specific region over two years?"

**Tests:** Complex aggregation, market share calculation, CASE statements, multi-year analysis

---

## Query 9: Product Type Profit Measure
**Question:** "Show the profit from line items containing a specific color part, broken down by nation and year."

**Tests:** Complex profit calculation, nation grouping, year extraction, color filtering

---

## Query 10: Returned Item Reporting
**Question:** "List the top 20 customers by revenue who have returned items, including their nation and account balance."

**Tests:** Revenue aggregation, TOP N, return flag filtering, customer details

---

## Query 11: Important Stock Identification
**Question:** "Find parts from suppliers in Germany with a total supply value exceeding a threshold."

**Tests:** HAVING clause, supplier nation filtering, supply value aggregation

---

## Query 12: Shipping Modes and Order Priority
**Question:** "Count high and low priority orders by shipping mode for MAIL and SHIP shipments received in 1994."

**Tests:** CASE statements, shipping mode filtering, priority classification, date ranges

---

## Query 13: Customer Distribution
**Question:** "Show the distribution of customers by the number of orders they have placed (including those with zero orders)."

**Tests:** LEFT JOIN, COUNT with GROUP BY, customer order patterns

---

## Query 14: Promotion Effect
**Question:** "What percentage of revenue in September 1994 came from promotional parts?"

**Tests:** Percentage calculation, CASE statement, part type filtering, revenue analysis

---

## Query 15: Top Supplier
**Question:** "Who is the supplier with the maximum total revenue in Q1 1996?"

**Tests:** View or CTE creation, MAX aggregation, date ranges, supplier ranking

---

## Query 16: Parts/Supplier Relationship
**Question:** "Count suppliers by part brand, type, and size, excluding specific supplier complaints and manufacturers."

**Tests:** NOT IN, negative filtering, multi-column GROUP BY, DISTINCT count

---

## Query 17: Small-Quantity-Order Revenue
**Question:** "What is the average yearly revenue loss if small quantity orders were eliminated for a specific part?"

**Tests:** Subquery with AVG, revenue calculation, quantity filtering

---

## Query 18: Large Volume Customer
**Question:** "List customers with orders containing more than 300 units in any single line item."

**Tests:** HAVING clause, GROUP BY with large thresholds, customer identification

---

## Query 19: Discounted Revenue
**Question:** "Calculate revenue from specific part brands/containers with certain quantity, shipping mode, and shipping instruction combinations."

**Tests:** Complex OR conditions, multiple BETWEEN clauses, specific value matching

---

## Query 20: Potential Part Promotion
**Question:** "Identify suppliers who have excess inventory of specific parts in Canada that were shipped to customers in 1994."

**Tests:** Complex subqueries, nation filtering, date ranges, inventory analysis

---

## Query 21: Suppliers Who Kept Orders Waiting
**Question:** "List suppliers in Saudi Arabia who had line items waiting (receipt date > commit date) for orders with multiple suppliers."

**Tests:** EXISTS with complex conditions, multi-table correlation, wait time analysis

---

## Query 22: Global Sales Opportunity
**Question:** "Count customers in each country code who have positive account balances but haven't placed orders in 7 years."

**Tests:** NOT EXISTS, substring operations, date arithmetic, account balance filtering

---

## Simplified Evaluation Queries

For practical evaluation, here are simplified versions:

### Basic Queries (Q1-Q6)
1. "Show pricing summary for line items by return flag and status"
2. "What is the total revenue from line items?"
3. "Show the top 10 orders by total price"
4. "How many orders are in each status?"
5. "What is revenue by region?"
6. "Show revenue for line items with quantity less than 24"

### Aggregation Queries (Q7-Q12)
7. "Calculate revenue by nation and year"
8. "What is the market share by region?"
9. "Show profit by nation and year"
10. "List top 20 customers by revenue"
11. "Find suppliers with highest supply value"
12. "Count orders by shipping mode"

### Complex Queries (Q13-Q18)
13. "Show distribution of customers by order count"
14. "What percentage of revenue comes from specific part types?"
15. "Who is the top supplier by revenue?"
16. "Count suppliers by part attributes"
17. "What is average revenue per order?"
18. "List customers with large orders (over 300 units)"

### Advanced Queries (Q19-Q22)
19. "Calculate revenue for specific part/shipping combinations"
20. "Identify suppliers with excess inventory"
21. "Find suppliers with delayed line items"
22. "Count customers with positive balances but no recent orders"

---

## Evaluation Criteria

For each query, evaluate:
1. **Correctness:** Does Dash generate valid SQL?
2. **Accuracy:** Does the SQL match the intent?
3. **Context Usage:** Did Dash search knowledge/learnings first?
4. **Insight Quality:** Does the response include interpretation?
5. **Learning:** Did errors trigger learning saves?

---

## Sources

- [TPC-H Queries - GitHub (Vonng/pgtpc)](https://github.com/Vonng/pgtpc/blob/master/tpch/queries/)
- [TPC-H Benchmark - StarRocks](https://docs.starrocks.io/docs/benchmarking/TPC-H_Benchmarking/)
- [TPC-H Benchmark - Apache Doris](https://doris.apache.org/docs/3.x/benchmark/tpch/)
- [TPC-H - PostgreSQL Wiki](https://wiki.postgresql.org/wiki/TPC-H)
