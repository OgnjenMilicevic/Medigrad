# Publishing Datagrad on GitHub — builds for Windows, Linux, and macOS

This guide takes you from "code on my computer" to "downloadable apps for every
platform," without owning a Mac or a Linux machine. GitHub builds all of them
for you on its own servers.

When you finish, every time you publish a version, GitHub automatically produces:

| Platform | Download | Runs on |
|----------|----------|---------|
| Windows  | `Datagrad-Windows-x64.zip`            | Windows 10/11 (64-bit) |
| Linux    | `Datagrad-Linux-x64.tar.gz`           | Most 64-bit desktop Linux |
| macOS Intel | `Datagrad-macOS-Intel.dmg`         | Intel Macs |
| macOS Apple Silicon | `Datagrad-macOS-AppleSilicon.dmg` | M1/M2/M3/M4 Macs |

You need: a free GitHub account, and Git installed on your computer. Nothing else.

---

## Part 1 — One-time setup

### 1.1 Create a free GitHub account

Go to https://github.com and sign up if you don't already have an account.

### 1.2 Install Git

- **Windows:** download from https://git-scm.com/download/win and run the
  installer (accept all the defaults).
- **macOS:** open Terminal and type `git --version`; if it isn't installed,
  macOS will offer to install it.
- **Linux:** `sudo apt install git` (or your distro's equivalent).

Verify it works — open a terminal / Command Prompt and run:

    git --version

You should see a version number.

### 1.3 Tell Git who you are (first time only)

    git config --global user.name "Your Name"
    git config --global user.email "you@example.com"

---

## Part 2 — Put the code on GitHub

### 2.1 Create an empty repository on GitHub

1. Log in to GitHub and click the **+** in the top-right → **New repository**.
2. **Repository name:** `datagrad` (or any name you like).
3. Choose **Private** (only you can see it) or **Public** (anyone can) — either
   works. Private is fine; the build still runs.
4. **Do NOT** check "Add a README", ".gitignore", or "license" — the project
   already has these.
5. Click **Create repository**.

GitHub now shows you a page with a URL like
`https://github.com/yourname/datagrad.git`. Keep it handy.

### 2.2 Upload the project

Unzip the Datagrad project somewhere on your computer. Open a terminal /
Command Prompt **inside that folder** (the one containing `app.py`,
`desktop_main.py`, and the `.github` folder), then run these commands one at a
time, replacing the URL with yours from step 2.1:

    git init
    git add .
    git commit -m "Initial commit"
    git branch -M main
    git remote add origin https://github.com/yourname/datagrad.git
    git push -u origin main

The first time you `push`, GitHub will ask you to log in. On Windows a browser
window pops up — just sign in. (If it asks for a password in the terminal, use
a **Personal Access Token**, not your account password — see Troubleshooting.)

Refresh your repository page on GitHub; you should now see all the files,
including a `.github` folder.

> **Important:** the `.github/workflows/build.yml` file is what makes the
> automatic builds work. Make sure it uploaded. If you don't see a `.github`
> folder on GitHub, the upload missed it — see Troubleshooting.

---

## Part 3 — Publish a version (this triggers the builds)

The workflow is set to build whenever you publish a **version tag** — a label
like `v1.0`. Here's the simplest way to do that.

### 3.1 Create and push a version tag

In the same terminal, inside the project folder:

    git tag v1.0
    git push origin v1.0

That's it. Pushing the tag kicks off the build.

### 3.2 Watch it build

1. On your GitHub repository page, click the **Actions** tab.
2. You'll see a run named **"Build Datagrad (all platforms)"** in progress.
3. Click it to watch. You'll see four parallel jobs — Windows, Linux, macOS
   Intel, macOS Apple Silicon — each turning green as it finishes.
4. The whole thing takes roughly **10–20 minutes** the first time.

### 3.3 Get your downloads

When all jobs finish, the workflow creates a **Release**:

1. Go to the **Releases** section (right-hand side of your repo's main page, or
   add `/releases` to your repo URL).
2. You'll see **v1.0** with all four files attached under "Assets":
   the Windows `.zip`, Linux `.tar.gz`, and two macOS `.dmg` files.
3. Download whichever you need, or share the Release page link with users so
   they can download the build for their own platform.

**Done.** You now have working apps for every platform, built entirely on
GitHub's servers.

---

## Part 4 — Publishing future versions

Whenever you change the code and want a new release:

    git add .
    git commit -m "Describe what changed"
    git push
    git tag v1.1
    git push origin v1.1

Each new tag (`v1.1`, `v1.2`, `v2.0`, …) builds and publishes a fresh release
automatically. Tag numbers must be unique — you can't reuse `v1.0`.

> **Tip:** you can also trigger a build *without* making a release. On the
> **Actions** tab, open the workflow and click **"Run workflow"**. That builds
> all platforms and leaves the files under the run's "Artifacts" (downloadable
> for 14 days) but does not create a public Release.

---

## What your users do with the downloads

- **Windows:** unzip `Datagrad-Windows-x64.zip`, open the `Datagrad` folder,
  double-click `Datagrad.exe`. On first run Windows shows a blue
  "Windows protected your PC" notice — click **More info → Run anyway**
  (this happens because the app isn't code-signed; it's expected).

- **macOS:** open the `.dmg`, drag `Datagrad.app` to Applications. First launch:
  right-click the app → **Open** → **Open** (this is needed once because the app
  isn't notarized by Apple; afterwards it opens normally).

- **Linux:** extract `tar -xzf Datagrad-Linux-x64.tar.gz`, then run
  `./Datagrad/Datagrad`. Most desktop distributions already have the required
  WebKitGTK library; if a window doesn't appear, the app falls back to opening
  in the default web browser.

---

## Troubleshooting

**The Actions tab shows no runs / no build started.**
The build only triggers on a tag that starts with `v`. Make sure you ran
`git push origin v1.0` (pushing the tag specifically), not just `git push`.

**I don't see the `.github` folder on GitHub.**
Some systems hide dot-folders. Confirm it's tracked by running
`git status` — if `.github/workflows/build.yml` isn't listed as committed,
run `git add .github` then commit and push again.

**Git asks for a password and rejects my account password.**
GitHub no longer accepts your login password over the command line. Create a
**Personal Access Token**: GitHub → your avatar → **Settings** →
**Developer settings** → **Personal access tokens** → **Tokens (classic)** →
**Generate new token**, give it the **repo** scope, and paste that token when
Git asks for a password. (Or install **GitHub Desktop**, a clickable app that
handles login for you: https://desktop.github.com)

**A macOS or Linux build job failed (red X).**
Open the failed job in the Actions tab and read the red step. The most common
cause is a transient dependency download hiccup — re-run by clicking
**Re-run jobs**. If a specific library fails to install, note which step and
which platform; that's the information needed to fix it.

**The build succeeded but my antivirus flags the Windows `.exe`.**
Unsigned PyInstaller apps occasionally get false-positive flags. This is a
known PyInstaller quirk, not a real infection. Code-signing removes it; until
then, users may need to allow the file in their antivirus.

**Can I build only one platform to save time?**
Yes. In `.github/workflows/build.yml`, delete the matrix entries you don't
want from the `include:` list, commit, and push a new tag.

---

## How it works (optional reading)

- `.github/workflows/build.yml` defines the automated build. GitHub reads it and
  spins up four fresh virtual machines — one per platform — runs PyInstaller on
  each, packages the result, and attaches everything to a Release.
- `Datagrad.spec` tells PyInstaller what to bundle. The same spec works on every
  platform; it detects macOS and produces a `.app` there.
- `desktop_main.py` is the program that runs: it starts the local server and
  opens the app in a native window (or the browser if no window backend exists).
- Nothing is ever exposed to the internet — the app talks only to itself on a
  private local port.
