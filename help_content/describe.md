# **Summary Statistics (Describe)**

The Describe feature generates a full [[descriptive statistics]] report for every column in your dataset.

## **How to Use**

1. Go to **Description > Describe**.
2. Datagrad computes summary statistics for all columns and displays them in a results table.

## **What Is Reported**

For **numeric columns**: count, [[mean]], [[standard deviation]], min, 25th percentile (Q1), [[median]], 75th percentile (Q3), max, [[skewness]], [[kurtosis]], and [[normality]] test results ([[Shapiro-Wilk test]], [[Lilliefors test]]).

For **categorical columns**: count, number of unique values, top category, and frequency of the top category.

## **Tips**

* Use this as a first step after loading data to understand your dataset's structure.
* If you need statistics broken down by a grouping variable, use **Grouped Summary Statistics** instead.
