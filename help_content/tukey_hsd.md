# **Tukey's HSD**

[[Tukey's HSD]] (Honestly Significant Difference) is a [[post-hoc test]] used after [[ANOVA]] to make all pairwise comparisons between group means while controlling the family-wise error rate.

## **When to Use It**

* Your ANOVA found a significant result and you want to know which specific groups differ.

## **Interpreting the Results**

* Each pairwise comparison shows the mean difference, a [[confidence interval]], and a [[p-value]].
* Pairs with p < 0.05 are significantly different from each other.

## **Tips**

* Tukey's HSD assumes equal variances and normality, like standard ANOVA.
* For the non-parametric equivalent, use [[Dunn's test]] after a [[Kruskal-Wallis test]].
