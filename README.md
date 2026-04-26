# PPT Master — AI generates natively editable PPTX from any document

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

English | [中文](./README_CN.md)

<p align="center">
  <a href="https://github.com/MorningStar0709/ppt-master-enhanced"><strong>Repository</strong></a> ·
  <a href="./examples/"><strong>Examples</strong></a> ·
  <a href="./docs/faq.md"><strong>FAQ</strong></a> ·
  <a href="./docs/technical-design.md"><strong>Technical Design</strong></a>
</p>

> **Repository status** — this repository is an independently maintained derivative of the original PPT Master project. It is maintained by [MorningStar0709](https://github.com/MorningStar0709) and is not the upstream official repository. Distributed under MIT with upstream attribution retained.

---

Drop in a PDF, DOCX, URL, or Markdown — get back a **natively editable PowerPoint** with real shapes, real text boxes, and real charts. Not images. Click anything and edit it.

**[Why PPT Master?](./docs/why-ppt-master.md)**

There's no shortage of AI presentation tools — what's missing is one where the output is **actually usable as a real PowerPoint file**. I build presentations every day, but most tools export images or web screenshots: they look nice but you can't edit anything. Others produce bare-bones text boxes and bullet lists. And they all want a monthly subscription, upload your files to their servers, and lock you into their platform.

PPT Master is different:

- **Real PowerPoint** — if a file can't be opened and edited in PowerPoint, it shouldn't be called a PPT. Every element PPT Master outputs is directly clickable and editable
- **Transparent, predictable cost** — the tool is free and open source; the main cost is your own AI editor usage. This derivative usually costs more time and tokens than the upstream project because it adds stricter checkpoints and review gates
- **Data stays local** — your files shouldn't have to be uploaded to someone else's server just to make a presentation. Apart from AI model communication, the entire pipeline runs on your machine
- **No platform lock-in** — your workflow shouldn't be held hostage by any single company. Works with Claude Code, Cursor, VS Code Copilot, and more; supports Claude, GPT, Gemini, Kimi, and other models

Compared with the upstream project, this derivative intentionally trades speed and token efficiency for more control and reliability. Expect longer runs and higher token usage because the workflow adds template selection, Eight Confirmations, sequential page generation with immediate self-review, and a blocking final SVG approval gate before export.

**See examples in [`examples/`](./examples/)** — 15 projects, 229 pages

## Gallery

<table>
  <tr>
    <td align="center"><img src="./docs/assets/screenshots/preview_magazine_garden.png" alt="Magazine style — Garden building guide" /><br/><sub><b>Magazine</b> — warm earthy tones, photo-rich layout</sub></td>
    <td align="center"><img src="./docs/assets/screenshots/preview_academic_medical.png" alt="Academic style — Medical image segmentation research" /><br/><sub><b>Academic</b> — structured research format, data-driven</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="./docs/assets/screenshots/preview_dark_art_mv.png" alt="Dark art style — Music video analysis" /><br/><sub><b>Dark Art</b> — cinematic dark background, gallery aesthetic</sub></td>
    <td align="center"><img src="./docs/assets/screenshots/preview_nature_wildlife.png" alt="Nature style — Wildlife wetland documentary" /><br/><sub><b>Nature Documentary</b> — immersive photography, minimal UI</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="./docs/assets/screenshots/preview_tech_claude_plans.png" alt="Tech style — Claude AI subscription plans" /><br/><sub><b>Tech / SaaS</b> — clean white cards, pricing table layout</sub></td>
    <td align="center"><img src="./docs/assets/screenshots/preview_launch_xiaomi.png" alt="Product launch style — Xiaomi spring release" /><br/><sub><b>Product Launch</b> — high contrast, bold specs highlight</sub></td>
  </tr>
</table>

---

## Maintained by MorningStar0709

This repository is a deeply customized, independently maintained derivative of the original PPT Master project. It focuses on a stricter production workflow, stronger Windows/Trae execution discipline, and an explicit SVG review gate before export.

Compared with the upstream project, this version adds a review/revision system, additional validators, tighter project-path rules, and more conservative export gating for higher reliability in real delivery workflows.

In practice, that also means this version is slower and more token-intensive than the upstream project. It is designed for controlled delivery quality rather than fastest possible draft generation.

🐙 Maintainer: [MorningStar0709](https://github.com/MorningStar0709)

---

## Quick Start

### 1. Prerequisites

**You need Conda plus Python 3.10+.** The workflow assumes a dedicated `ppt-master` Conda environment, and all project commands run through `conda run -n ppt-master ...`.

| Dependency | Required? | What it does |
|------------|:---------:|--------------|
| [Miniconda / Conda](https://docs.conda.io/en/latest/miniconda.html) | ✅ **Yes** | Creates and runs the required `ppt-master` environment |
| [Python](https://www.python.org/downloads/) 3.10+ | ✅ **Yes** | Runtime version used inside the Conda environment |

> **TL;DR** — Install Conda, create `ppt-master` with Python 3.10+, then run `conda run -n ppt-master pip install -r requirements.txt`.

<details open>
<summary><strong>Windows</strong> — see the dedicated step-by-step guide ⚠️</summary>

Windows requires a few extra steps (PATH setup, execution policy, etc.). We wrote a **step-by-step guide** specifically for Windows users:

**📖 [Windows Installation Guide](./docs/windows-installation.md)** — from zero to a working presentation in 10 minutes.

Quick version: install Miniconda → create the environment with `conda create -n ppt-master python=3.10 -y` → run `conda run -n ppt-master pip install -r requirements.txt`.
</details>

<details>
<summary><strong>macOS / Linux</strong> — install and go</summary>

```bash
# macOS
brew install --cask miniconda
conda create -n ppt-master python=3.10 -y
conda run -n ppt-master pip install -r requirements.txt

# Ubuntu / Debian
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o miniconda.sh
bash miniconda.sh -b -p "$HOME/miniconda3"
"$HOME/miniconda3/bin/conda" create -n ppt-master python=3.10 -y
conda run -n ppt-master pip install -r requirements.txt
```
</details>

<details>
<summary><strong>Edge-case fallbacks</strong> — 99% of users don't need these</summary>

Two external tools exist as fallbacks for edge cases. **Most users will never need them** — install only if you hit one of the specific scenarios below.

| Fallback | Install only if… |
|----------|-----------------|
| [Node.js](https://nodejs.org/) 18+ | You need to import WeChat Official Account articles **and** `curl_cffi` (part of `requirements.txt`) has no prebuilt wheel for your Python + OS + CPU combination. In normal setups `web_to_md.py` handles WeChat directly through `curl_cffi`. |
| [Pandoc](https://pandoc.org/) | You need to convert legacy formats: `.doc`, `.odt`, `.rtf`, `.tex`, `.rst`, `.org`, or `.typ`. `.docx`, `.html`, `.epub`, `.ipynb` are handled natively by Python — no pandoc required. |

```bash
# macOS (only if the above conditions apply)
brew install node
brew install pandoc

# Ubuntu / Debian
sudo apt install nodejs npm
sudo apt install pandoc
```
</details>

### 2. Pick an AI Editor

| Tool | Rating | Notes |
|------|:------:|-------|
| **[Claude Code](https://claude.ai/)** | ⭐⭐⭐ | Best results — native Opus, largest context |
| [Cursor](https://cursor.sh/) / [VS Code + Copilot](https://code.visualstudio.com/) | ⭐⭐ | Good alternatives |
| Codebuddy IDE | ⭐⭐ | Best for Chinese models (Kimi 2.5, MiniMax 2.7) |

### 3. Set Up

**Option A — Download ZIP** (no Git required): click **Code → Download ZIP** on the [GitHub page](https://github.com/MorningStar0709/ppt-master-enhanced), then unzip.

**Option B — Git clone** (requires [Git](https://git-scm.com/downloads) installed):

```bash
git clone https://github.com/MorningStar0709/ppt-master-enhanced.git
cd ppt-master
```

Then install dependencies:

```bash
conda create -n ppt-master python=3.10 -y
conda run -n ppt-master pip install -r requirements.txt
```

To update later (Option B only, with a clean tracked worktree): `conda run -n ppt-master python skills/ppt-master-enhanced/scripts/update_repo.py`

### 4. Create

**Provide source materials (recommended):** Place your PDF, DOCX, images, or other files in the `projects/` directory, then tell the AI chat panel which files to use. The quickest way to get the path: right-click the file in your file manager or IDE sidebar → **Copy Path** (or **Copy Relative Path**) and paste it directly into the chat.

```
You: Please create a PPT from projects/q3-report/sources/report.pdf
```

**Paste content directly:** You can also paste text content straight into the chat window and the AI will generate a PPT from it.

```
You: Please turn the following into a PPT: [paste your content here...]
```

Either way, the AI will first confirm the design spec:

```
AI:  Sure. Let's confirm the design spec:
     [Template] B) Free design
     [Format]   PPT 16:9
     [Pages]    8-10 pages
     ...
```

The AI handles content analysis, visual design, and sequential SVG generation, but PPTX export is gated by an explicit final SVG review approval.

> **Output:** After Step 7 final SVG approval, two timestamped files are saved to `exports/` — a native-shapes `.pptx` (directly editable) and an `_svg.pptx` snapshot for visual reference. Requires Office 2016+.

> **Time & token trade-off:** This derivative is intentionally slower and usually consumes more tokens than the upstream project. The extra cost comes from stricter checkpoints, page-by-page self-review, review/revision bookkeeping, and export gating.

> **AI lost context?** Ask it to read `skills/ppt-master-enhanced/SKILL.md`.

> **Something went wrong?** Check the **[FAQ](./docs/faq.md)** — it covers model selection, layout issues, export problems, and more. Continuously updated from real user reports.

### 5. AI Image Generation (Optional)

```bash
cp .env.example .env    # then edit with your API key
```

Use the repository-root `.env` only. `.trae/.env` is not supported.

```env
IMAGE_BACKEND=<provider>                   # required — must be set explicitly
GEMINI_API_KEY=your-api-key
GEMINI_MODEL=gemini-3.1-flash-image-preview
```

Supported backends: `gemini` · `openai` · `qwen` · `zhipu` · `volcengine` · `stability` · `bfl` · `ideogram` · `siliconflow` · `fal` · `replicate`

Common examples:
- `IMAGE_BACKEND=gemini`
- `IMAGE_BACKEND=openai`
- `IMAGE_BACKEND=qwen`
- `IMAGE_BACKEND=minimax`

Run `conda run -n ppt-master python skills/ppt-master-enhanced/scripts/image_gen.py --list-backends` to see tiers. Environment variables override the repository-root `.env`. Use provider-specific keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, etc.) — global `IMAGE_API_KEY` is not supported.

> **Tip:** For best quality, generate images in [Gemini](https://gemini.google.com/) and select **Download full size**. Remove the watermark with `scripts/gemini_watermark_remover.py`.

---

## Documentation

| | Document | Description |
|---|----------|-------------|
| 🆚 | [Why PPT Master](./docs/why-ppt-master.md) | How it compares to Gamma, Copilot, and other AI tools |
| 🪟 | [Windows Installation](./docs/windows-installation.md) | Step-by-step setup guide for Windows users |
| 📖 | [SKILL.md](./skills/ppt-master-enhanced/SKILL.md) | Core workflow and rules |
| 🔍 | [Skill Comparison Report](./skill_compare_20260426_221639.md) | What changed compared with the upstream `hugohe3/ppt-master` skill |
| 📐 | [Canvas Formats](./skills/ppt-master-enhanced/references/canvas-formats.md) | PPT 16:9, Xiaohongshu, WeChat, and 10+ formats |
| 🛠️ | [Scripts & Tools](./skills/ppt-master-enhanced/scripts/README.md) | All scripts and commands |
| 💼 | [Examples](./examples/README.md) | 15 projects, 229 pages |
| 🏗️ | [Technical Design](./docs/technical-design.md) | Architecture, design philosophy, why SVG |
| ❓ | [FAQ](./docs/faq.md) | Model selection, cost, layout troubleshooting, custom templates |

---

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for how to get involved.

## License

[MIT](LICENSE)

## Upstream Attribution

This repository is based on the original PPT Master project created by Hugo He.

- Upstream project: [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)
- This repository: independently maintained derivative by [MorningStar0709](https://github.com/MorningStar0709)

## Acknowledgments

[SVG Repo](https://www.svgrepo.com/) · [Tabler Icons](https://github.com/tabler/tabler-icons) · [Robin Williams](https://en.wikipedia.org/wiki/Robin_Williams_(author)) (CRAP principles) · McKinsey, BCG, Bain

## Contact & Collaboration

Looking to collaborate, adapt the workflow, or report issues?

- 💬 **Questions & sharing** — [GitHub Discussions](https://github.com/MorningStar0709/ppt-master-enhanced/discussions)
- 🐛 **Bug reports & feature requests** — [GitHub Issues](https://github.com/MorningStar0709/ppt-master-enhanced/issues)
- 📧 **Contact email** — [fanpuji55@outlook.com](mailto:fanpuji55@outlook.com)
- 🐙 **Maintainer profile** — [MorningStar0709](https://github.com/MorningStar0709)

---

Maintained by [MorningStar0709](https://github.com/MorningStar0709) · Based on the original PPT Master project by Hugo He

[⬆ Back to Top](#ppt-master--ai-generates-natively-editable-pptx-from-any-document)

