# **Variables**

In statistics, a **variable** is any characteristic that can be measured or categorized. Datagrad works with three main types of variable:

## **Continuous (Numeric) Variables**

A [[continuous variable]] can take any value within a range — for example, age (25.3), blood pressure (120.5), or income (48 200). These variables are suitable for calculations like [[mean]], [[standard deviation]], and [[correlation]].

## **Categorical Variables**

A [[categorical variable]] contains a finite number of distinct groups — for example, blood type (A, B, AB, O) or treatment group (placebo, drug). Datagrad identifies these automatically when a column contains non-numeric text or a small number of unique values.

## **Ordinal Variables**

An [[ordinal variable]] is a special kind of categorical variable where the categories have a natural order (e.g. mild → moderate → severe), but the distances between categories are not assumed to be equal.

## **Binary Variables**

A [[binary variable]] has exactly two possible values (e.g. yes/no, 0/1, male/female). Some tests and models treat binary variables differently from multi-level categories.

## **Why It Matters in Datagrad**

The type of each variable determines which statistical tests and visualizations are appropriate. Datagrad detects types automatically, but you can override them using [[type casting]] if needed.
