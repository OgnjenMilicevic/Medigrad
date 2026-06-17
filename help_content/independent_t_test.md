# **Independent T-Test**

The [[independent t-test]] compares the [[mean]]s of two **unrelated** groups to determine whether they are statistically different.

## **How to Use**

1. Go to **Analysis > Tests > Independent T-Test**.
2. Select the **Group Column** (a [[binary variable]] with exactly two groups).
3. Select the **Value Column** (the [[continuous variable]] to compare).

## **Assumptions**

* The two groups are independent (different subjects in each group).
* The value column is approximately [[normality|normally distributed]] within each group.
* Variances are approximately equal across groups (checked with [[Levene's test]]).

## **Interpreting the Results**

* **t-statistic** — How many standard errors the group means are apart.
* **[[p-value]]** — If below 0.05, the difference is statistically significant.
* **[[confidence interval]]** — The range in which the true difference in means likely falls.

## **Tips**

* If normality is violated, use the [[Mann-Whitney U test]] instead.
* If variances are unequal, Datagrad's smart analysis will flag this.
