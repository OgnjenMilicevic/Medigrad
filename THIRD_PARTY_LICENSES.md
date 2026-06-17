# Third-Party Licenses

Datagrad bundles the following third-party components, all under permissive
licenses that allow free use, including in fee-charging educational settings.

## Front-end libraries (in `vendor/`)

| Library      | Version | License | Notes |
|--------------|---------|---------|-------|
| Tabulator    | 6.4.0   | MIT     | Data grid (spreadsheet view + manual entry) |
| Plotly.js    | 2.32.0  | MIT     | Charts (correlation heatmap, regression plot) |
| Tailwind CSS | 3.x     | MIT     | Styling (compiled to a static stylesheet) |

## Python libraries (installed from requirements.txt)

| Library   | License        |
|-----------|----------------|
| Flask     | BSD-3-Clause   |
| Werkzeug  | BSD-3-Clause   |
| Jinja2    | BSD-3-Clause   |
| NumPy     | BSD-3-Clause   |
| pandas    | BSD-3-Clause   |
| SciPy     | BSD-3-Clause   |
| openpyxl  | MIT            |
| pyreadstat| Apache-2.0     |
| Markdown  | BSD-3-Clause   |
| waitress  | ZPL-2.1        |
| pywebview | BSD-3-Clause   |

All of the above permit redistribution and commercial/educational use. None
impose a per-seat or commercial-use fee.

> Note: an earlier build used Handsontable for the data grid, which requires a
> paid license for commercial use. It was replaced with Tabulator (MIT) so the
> application can be distributed freely, including in paid-tuition courses,
> without any licensing obligation.

Each library's full license text is available in its own distribution and at
its project homepage.
