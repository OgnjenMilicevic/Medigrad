# **The Data Grid**

The data grid is the central workspace in Datagrad. It is powered by [[Handsontable]] and provides an Excel-like editing experience.

## **Features**

* **Edit cells** directly by clicking on them and typing a new value.
* **Edit columns** by right-clicking a column header to access options like [[type casting]], [[recoding]], [[encoding]], and [[row exclusion]].
* **Delete rows** by selecting them and using the context menu.
* **Sort and navigate** through your data as you would in a spreadsheet.

## **How It Works**

All edits are synchronized with the Python backend in real time. When you change a cell value, the underlying DataFrame is updated immediately, ensuring that any analysis you run reflects the latest state of your data.

## **Tips**

* Row numbers displayed in the grid use 1-based indexing (row 1 is the first row of data).
* The status bar at the bottom shows the current row and column counts, including how many rows are active vs. excluded.
