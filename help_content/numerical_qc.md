# **Numerical QC Report**

[[Numerical QC]] (Quality Control) is a diagnostic report that examines every numeric column for data quality issues.

## **How to Use**

1. Go to **Description > Numerical QC**.
2. Datagrad scans each numeric column and produces a report.

## **What It Checks**

* **[[Outlier]]s (IQR method)** — Values below Q1 − 1.5×[[IQR]] or above Q3 + 1.5×IQR.
* **[[Outlier]]s (Standard deviation method)** — Values more than 3 [[standard deviation]]s from the [[mean]].
* **[[Constant increment pattern]]s** — Sequences that increase or decrease by a fixed step, which may indicate row-number artifacts or index columns rather than genuine measurements.

## **Interpreting the Results**

Each column's entry lists the number of outliers detected by each method, plus any constant increment findings. A column with many outliers may need investigation — are they genuine extreme values, or data entry errors?

## **Tips**

* Run the QC report early in your workflow to catch problematic columns before analysis.
* Not all outliers need to be removed — they may represent real, important data. Use your domain knowledge to decide.
