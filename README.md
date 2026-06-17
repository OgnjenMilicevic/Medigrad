# Datagrad MFUB Desktop

> All web libraries (Tailwind, Tabulator, Plotly — all MIT-licensed) are bundled locally, so the app works fully offline and can be distributed freely, including in paid courses. See THIRD_PARTY_LICENSES.md.

A trimmed, offline desktop edition of Datagrad containing only the core
statistical tests:

- **Correlation** — Pearson, Spearman (with auto heatmap)
- **Simple linear regression** — one predictor, with coefficient table,
  95% confidence intervals, R²/adjusted R², and a scatter plot with the
  fitted regression line
- **t-tests** — one-sample, independent, paired
- **Nonparametric counterparts** — one-sample sign test, Mann–Whitney U, Wilcoxon signed-rank
- **ANOVA** — one-way (with Tukey HSD post-hoc when significant)
- **Kruskal–Wallis** (with pairwise Mann–Whitney post-hoc when significant)
- **Chi-square** test of independence
- **Chi-square goodness-of-fit (1-way)** — test a single categorical column, or manually-entered observed frequencies, against expected counts/ratios (or uniform if left blank)
- **McNemar's test** — paired/related categorical (2x2), with a choice of
  exact (binomial) or chi-square (continuity-corrected) method
- **Fisher exact** test
- **Diagnostic test evaluation** — sensitivity, specificity, PPV/NPV (with
  prevalence-adjusted predictive values), likelihood ratios, and 95% CIs
- **Description extras** — coefficient of variation in the scale table and a
  dedicated normality-tests table (Shapiro-Wilk + Kolmogorov-Smirnov)

Everything else from the original web app (regression, factor analysis,
questionnaire/reliability, mediation/moderation, power analysis, diagnostics,
the smart-method router, all graphing, data wrangling/imputation, Redis,
async job workers, rate limiting, Docker/cloud deploy) has been removed.

The app runs as a native Windows window. There is no browser tab, no console,
and nothing is exposed to the network — the server listens only on a private
127.0.0.1 port chosen at launch.

---

## What you can do in the app

The **MFUB** menu holds course materials specific to the Faculty of Medicine, University of Belgrade. Add files to the `mfub/` folder and list them in `mfub/manifest.json` (markdown, files, or links).


1. **File → Set Session ID** — enter your name or student number; it is stamped on every logged action.
2. **File → New Blank Dataset** — create an empty grid (you choose rows, columns, and names) and type values directly, Excel-style. Numeric columns are detected automatically as you type.
3. **File → Upload File…** — load a .csv, .xlsx, .xls, .sav, or .pkl.
3. **File → Load Example Data** — three built-in teaching datasets (Clinical Trial, Teaching Methods, Health Survey) that exercise every test.
4. **Description →** Descriptive Statistics (optionally grouped) and a Numerical QC Report.
5. **Analysis →** pick a test; fill in the column picker dialog; read results.
6. **File → Download as CSV / XLSX** — export the current data grid.
7. **File → Show Activity Log Folder** — see where the local audit trail is saved.

### Activity log (for classes / exams)

Every analysis is appended to a local, per-user activity log in the user's
`Datagrad` home folder, as both `datagrad_activity.log` (readable) and
`datagrad_activity.csv` (opens in a spreadsheet). Each entry records the
timestamp, Session ID, test, chosen columns, and the headline result
(statistic + p-value). Set the log folder with the `DATAGRAD_LOG_DIR`
environment variable if you want it written somewhere specific. Note: this is
an integrity aid and convenience record, not tamper-proof proctoring.

The navigation bar carries the institutional logos (Katedra za medicinsku
statistiku i informatiku and Medicinski fakultet Univerziteta u Beogradu) on a
co-branding plate on the right.

---

## Building for all platforms (Windows, Linux, macOS)

The easiest way to produce apps for **every** platform — including Mac —
without owning each machine is to let GitHub build them for you. See
**PUBLISHING.md** for a complete, beginner-friendly walkthrough: push the
code to GitHub, push a version tag, and GitHub produces downloadable
Windows, Linux, Intel-Mac, and Apple-Silicon-Mac builds automatically and
attaches them to a Release.

The sections below cover building locally on a single machine instead.

## Building the Windows .exe

You need a **64-bit Python 3.11 or 3.12** on the Windows machine.

### Quick path (automated)

From a Command Prompt in this folder:

    build_windows.bat

This creates a virtual environment, installs dependencies + PyInstaller, and
produces the portable app at:

    dist\Datagrad\Datagrad.exe

Double-click that .exe to run — it is fully self-contained.

### Making an installer

Wrap the portable folder into a single setup installer with Inno Setup
(https://jrsoftware.org/isinfo.php):

1. Install Inno Setup.
2. Compile the included script:

       ISCC.exe Datagrad.iss

3. The installer appears at Output\Datagrad-Setup.exe. It installs per-user,
   adds a Start-menu (and optional desktop) shortcut, and registers an
   uninstaller — no admin rights required.

### Manual build

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt pyinstaller
    pyinstaller Datagrad.spec --noconfirm

#### One-file vs one-folder

Datagrad.spec builds a one-folder app by default (faster startup). For a single
Datagrad.exe, open Datagrad.spec and set ONEFILE = True, then rebuild.

#### Custom icon (optional)

Drop a datagrad.ico in this folder before building and it is used automatically.

---

## Running from source (any OS, for development)

    pip install -r requirements.txt
    python app.py            # serves on http://127.0.0.1:5000

Native-window version (needs pywebview):

    python desktop_main.py

---

## File map

| File / folder           | Purpose                                          |
|-------------------------|--------------------------------------------------|
| desktop_main.py         | Desktop entry point (waitress + native window)   |
| app.py                  | Flask app: routes, static serving, session store |
| individual_methods.py   | The nine basic statistical tests                 |
| correlation.py          | Pearson / Spearman correlation matrices          |
| blueprints/             | data (upload/download), analysis, help_bp        |
| app_state.py, serializers.py, session_store.py, inputting.py, plots.py | supporting infrastructure |
| index.html, style.css, js/, help_content/ | front-end assets               |
| requirements.txt        | runtime dependencies (lean)                      |
| Datagrad.spec           | PyInstaller build spec                           |
| Datagrad.iss            | Inno Setup installer script                      |
| build_windows.bat       | one-shot build script                            |

---

## Notes

- Dormant data-wrangling and plotting modal markup still exists in index.html
  but is no longer reachable from any menu, so it has no user-facing effect.
  It was left in place to avoid destabilizing the data grid and upload flow.
- Session data (your uploaded table) lives only in memory and is cleared when
  the app closes.
