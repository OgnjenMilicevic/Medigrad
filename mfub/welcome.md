# Welcome to Datagrad MFUB Desktop

This application was prepared for teaching **Medical Statistics** at the
**Faculty of Medicine, University of Belgrade**
(*Medicinski fakultet Univerziteta u Beogradu*),
**Department of Medical Statistics and Informatics**
(*Katedra za medicinsku statistiku i informatiku*).

## How to use this tab

The **MFUB** menu holds materials specific to our course. To add your own:

1. Put files (Markdown `.md`, PDF, images, or any document) into the
   `mfub/` folder next to the application.
2. Add an entry for each in `mfub/manifest.json`:
   - `"type": "markdown"` with a `"file"` — shown formatted inside the app.
   - `"type": "link"` with a `"url"` — opens a web page.
   - `"type": "file"` with a `"file"` — opens/downloads any other document
     (PDF, slides, etc.).
3. Restart the app (or rebuild it) and the items appear in the MFUB menu.

## Course statistics methods available

Use the **Description** and **Analysis** menus for the full set of tests:
descriptive statistics with coefficient of variation and normality tests,
correlation and regression, t-tests and their nonparametric counterparts,
ANOVA and Kruskal-Wallis, chi-square (independence and goodness-of-fit),
Fisher exact, McNemar, the one-sample sign test, and diagnostic test
evaluation (sensitivity, specificity, predictive values).
