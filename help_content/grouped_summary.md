# **Grouped Summary Statistics**

[[Grouped summary]] statistics compute descriptive measures separately for each level of one or more grouping variables, allowing you to compare distributions across categories.

## **How to Use**

1. Go to **Description > Describe** and specify one or more group columns.
2. Datagrad splits the data by the group columns and computes [[descriptive statistics]] within each group.

## **Interpreting the Results**

The output table has one row per group (or group combination if multiple grouping columns are selected). Each row shows the count, [[mean]], [[standard deviation]], [[median]], and other summary measures for the numeric columns in that group.

## **Tips**

* Use this to compare treatment vs. control groups, or to inspect differences across demographic categories before running formal statistical tests.
* Large differences in group [[mean]]s or [[standard deviation]]s may motivate a formal comparison test like a [[t-test]] or [[ANOVA]].
