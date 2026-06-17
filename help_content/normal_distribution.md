# **Normal Distribution**

The [[normal distribution]] (also called the [[bell curve]]) is the most important distribution in statistics. It is symmetric around its [[mean]] and fully described by two parameters: the mean (center) and the [[standard deviation]] (spread).

## **Why It Matters**

Many [[parametric test]]s — including the [[t-test]], [[ANOVA]], and [[linear regression]] — assume that the data (or the residuals) are approximately normally distributed. When this assumption is violated, [[non-parametric test]]s may be more appropriate.

## **Checking Normality in Datagrad**

Datagrad automatically checks normality using two tests:

1. **[[Shapiro-Wilk test]]** — Recommended for small to moderate samples (n < 5000).
2. **[[Lilliefors test]]** — A version of the Kolmogorov-Smirnov test suitable when the mean and variance are estimated from the data.

You can also visually assess normality using a [[QQ plot]] or a [[histogram]].

## **What If My Data Are Not Normal?**

If the normality assumption is not met, Datagrad's smart analysis features will automatically choose non-parametric alternatives (e.g. [[Mann-Whitney U test]] instead of a t-test, or [[Kruskal-Wallis test]] instead of ANOVA).
