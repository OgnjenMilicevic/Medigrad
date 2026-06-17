# **One-Way ANOVA**

[[ANOVA]] (Analysis of Variance) tests whether the [[mean]]s of **three or more** groups are equal.

## **How to Use**

1. Go to **Analysis > Tests > ANOVA**.
2. Select the **Group Column** (a [[categorical variable]] with 3+ levels).
3. Select the **Value Column** (a [[continuous variable]]).

## **Assumptions**

* The data within each group are approximately [[normality|normally distributed]].
* The variances across groups are approximately equal ([[homogeneity of variance]], checked with [[Levene's test]]).
* The groups are independent.

## **Interpreting the Results**

* **F-statistic** — The ratio of between-group variance to within-group variance.
* **[[p-value]]** — If significant, at least one group mean differs from the others.
* A significant ANOVA result tells you *something* differs, but not *which* groups. Use a [[post-hoc test]] (e.g. [[Tukey's HSD]]) to find the specific pairs.

## **Tips**

* If variances are unequal, use [[Welch's ANOVA]] instead.
* If normality is violated, use the [[Kruskal-Wallis test]] instead.
