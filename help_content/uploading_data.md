# **Uploading Data**

Datagrad supports several file formats for data import.

## **Supported Formats**

* **CSV** — Comma-separated values (`.csv`)
* **Excel** — `.xls` and `.xlsx` workbooks
* **SPSS** — IBM SPSS `.sav` files, including variable labels and metadata
* **Pickle** — Python `.pkl` serialized DataFrames

## **How to Use**

1. Click the **Upload** button in the toolbar.
2. Select a file from your computer.
3. The data will load into the interactive grid. Column types are automatically detected.

## **Tips**

* For [[SPSS file]]s, Datagrad extracts variable labels and value labels when available.
* If a column's type is detected incorrectly, you can change it with [[type casting]].
* Very large files may take a moment to load — the status bar will update you on progress.
