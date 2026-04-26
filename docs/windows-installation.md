# Windows Installation Guide

This guide walks you through installing PPT Master on Windows step by step. Follow along and you'll have a working setup in under 10 minutes.

---

## Step 1 — Install Conda (Required)

Conda is the only hard requirement for this workflow.

1. Install **Miniconda** (recommended) or **Anaconda**:
   - Miniconda: [docs.conda.io/miniconda](https://docs.conda.io/en/latest/miniconda.html)
   - Anaconda: [anaconda.com/download](https://www.anaconda.com/download)

2. Open **PowerShell** and create the required environment:

   ```powershell
   conda create -n ppt-master python=3.12 -y
   ```

3. Verify the environment:

   ```powershell
   conda run -n ppt-master python --version
   ```

   You should see `Python 3.12.x` (or another 3.10+ version).

---

## Step 2 — Download the Project

**Option A — Download ZIP** (easiest):

1. Go to [github.com/hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)
2. Click the green **Code** button → **Download ZIP**
3. Unzip to `C:\Users\YourName\ppt-master`

**Option B — Git Clone** (requires [Git](https://git-scm.com/downloads)):

```powershell
git clone https://github.com/hugohe3/ppt-master.git
cd ppt-master
```

---

## Step 3 — Install Dependencies

```powershell
cd C:\Users\YourName\ppt-master   # ← adjust to your actual path
conda run -n ppt-master pip install -r requirements.txt
```

> If `pip` is not recognized, try `conda run -n ppt-master python -m pip install -r requirements.txt`.

Wait for it to finish. You should see `Successfully installed ...` at the end.

---

## Step 4 — Verify Your Setup

```powershell
conda run -n ppt-master python -c "import pptx; import fitz; print('All core dependencies OK')"
```

✅ Output: `All core dependencies OK` → you're good.

❌ Error → see [Troubleshooting](#troubleshooting) below.

---

## Step 5 — Run a Minimal Example

Open your AI editor (Cursor, VS Code + Copilot, etc.), open the `ppt-master` folder, and type in the chat:

```
Please create a simple 3-page test PPT with a cover, one content page, and a closing page. Topic: "Hello World".
```

If a `.pptx` file appears in `exports/` that opens in PowerPoint — **you're done.**

---

## Step 6 — Optional Enhancements (most users can skip this)

With Python and `requirements.txt` installed, you already have everything needed to generate presentations. The items below are **edge-case fallbacks and enhancements** — install only if you hit the specific scenario.

| Enhancement | Install only if… | How to install | Verify |
|-------------|-----------------|----------------|--------|
| **CairoSVG** — higher quality PNG fallbacks | You want crisper PNG fallbacks for Office versions that don't render SVG natively. `svglib` (already installed) is fine for most cases. | Install [GTK3 Runtime](https://github.com/nickvdp/gtk3/releases), then `conda run -n ppt-master pip install cairosvg` | `conda run -n ppt-master python -c "import cairosvg"` |
| **Node.js** 18+ — WeChat fallback | You need to import WeChat Official Account articles **and** `curl_cffi` (part of `requirements.txt`) has no wheel for your Python version. Normally `web_to_md.py` handles WeChat through `curl_cffi`. | Download LTS from [nodejs.org](https://nodejs.org/) | `node --version` → v18+ |
| **Pandoc** — legacy document formats | You need to convert `.doc`, `.odt`, `.rtf`, `.tex`, `.rst`, `.org`, or `.typ`. `.docx`/`.html`/`.epub`/`.ipynb` work natively in Python. | Download `.msi` from [pandoc.org](https://pandoc.org/installing.html) | `pandoc --version` |

---

## Troubleshooting

### `python` was not found or opens Microsoft Store

**Cause**: Python isn't in your system PATH.

**Fix 1** — Re-run the Python installer → **Modify** → check **"Add Python to environment variables"**.

**Fix 2** — Manually add to PATH:
1. Run `where python` in PowerShell first to find the actual path (e.g. `C:\Users\YourName\AppData\Local\Programs\Python\Python312\python.exe`)
2. Search "Environment Variables" in Start menu
3. Find `Path` → **Edit** → add the **directory** from step 1 and its `Scripts` subfolder:
   ```
   C:\Users\YourName\AppData\Local\Programs\Python\Python312
   C:\Users\YourName\AppData\Local\Programs\Python\Python312\Scripts
   ```
4. Click OK, then **restart PowerShell**

**Fix 3** — Verify interpreter in the target env: `conda run -n ppt-master python --version`.

### `conda run -n ppt-master pip install` fails with permission errors

```powershell
conda run -n ppt-master pip install --user -r requirements.txt
```

Or run PowerShell as Administrator.

### `conda run -n ppt-master pip install` fails due to network issues

```powershell
conda run -n ppt-master pip install -r requirements.txt --proxy http://your-proxy:port
```

### `ModuleNotFoundError`

`pip` installed to a different Python. Use `conda run -n ppt-master python -m pip install -r requirements.txt` to match.

### `import fitz` fails

1. Upgrade pip: `conda run -n ppt-master python -m pip install --upgrade pip`
2. Pre-built wheel: `conda run -n ppt-master pip install PyMuPDF --only-binary :all:`
3. Still failing → install [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

### PowerShell says "running scripts is disabled"

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Still stuck?

- 📖 [FAQ](./faq.md)
- 🐛 [GitHub Issues](https://github.com/hugohe3/ppt-master/issues) — include your Python version, Windows version, and full error message
- 💬 [GitHub Discussions](https://github.com/hugohe3/ppt-master/discussions)
