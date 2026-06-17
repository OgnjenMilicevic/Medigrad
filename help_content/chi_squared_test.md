# **Chi-Squared Test**

The [[chi-squared test]] evaluates whether two [[categorical variable]]s are independent of each other.

## **How to Use**

1. Go to **Analysis > Tests > Chi-Squared Test**.
2. Select two categorical columns.

## **Interpreting the Results**

* The test compares **observed** cell frequencies in a contingency table to the frequencies **expected** under independence.
* A significant [[p-value]] (< 0.05) means the variables are associated.
* Report [[Cramér's V]] as an [[effect size]] alongside the chi-squared result.

## **Assumptions**

* Expected cell counts should generally be at least 5 in most cells. If many cells have small expected counts, use [[Fisher's exact test]] instead.
