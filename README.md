# Project RIAS — Research/AI Assistant

Turn research PDFs into production-ready assets.
Upload once → **DOCX summary** (figures in the right spots), **LAB Python code exercises**, **step-by-step slides**, and an **Excel workbook** with clean result tables. 

> Local **TypeScript** UI • Equation-safe extraction • No hallucinated facts • Repeatable templates

## ✨ Features

* **3 outputs from 1 upload**

  * **DOCX**: concise summary, **correct figure placement**, brief notes + 100–200-word explanations (optional).
  * **PPTX**: teaching-style slides that explain concepts gradually.
  * **LAB** : Python code exercises, if you have no programming knowledge, Rias can still help you understand and operate simply.  
  * **XLSX**: structured results (metrics, datasets, params), ready for SOTA comparisons.
* **Equation fidelity**: preserves symbols/relationships; extracts metrics **exactly as written**.
* **Deterministic templates**: strict prompts reduce drift and keep content faithful to the PDF.
* **Local workflow**: runs on your machine; works with OpenAI-compatible APIs.
* **CV-friendly**: great for detection/segmentation papers (mAP variants, IoU, Dice, loss terms, etc.).

---

## 🧭 Architecture (high level)

```
[PDF Upload]
    ↓
[Extractor]  — parse text/figures → normalize blocks
    ↓
[Prompt Orchestrator (.ts)]
    ├─ Summary template  → DOCX Exporter
    ├─ Slides template   → PPTX Exporter
    ├─ Lab template   → LAB Exporter
    └─ Results template  → XLSX Exporter
    (equation guardrails + metric validators)
    ↓
[Outputs/: docx | pptx | lab | xlsx]
```

---

## 🔧 Requirements

* Node.js 18+ (or 20+)
* (Optional) Python 3.10+ if you use local helpers for PDF parsing
* An LLM API key (e.g., `OPENAI_API_KEY` or compatible)

---

## 🚀 Quick Start

```bash
# 1) Clone
git clone https://github.com/essor1234/-Project-Rias_Assistant.git
cd -Project-Rias_Assistant

# 2) Install
npm install    # or pnpm install / yarn

# 3) Configure
cp .env.example .env
# add your OPENAI_API_KEY (or provider-compatible key)

# 4) Run
npm run dev    # launches local TypeScript UI
```

Open the local URL shown in the terminal.

---

## 🖱️ How to Use

1. **Upload PDF** (single paper to start).
2. Choose outputs (**DOCX / PPTX / LAB / XLSX**) and options:

   * “Preserve Equations” (on)
   * “Figure Alignment” (on)
   * “Slide Depth” (2–3 slides per concept)
3. Click **Generate**.
4. Download files from the **Outputs** panel.

---

## 📦 Output Details

* **DOCX**

  * Sections follow paper flow; images inserted near their original paragraph windows.
  * Optional: under each figure, a **brief note** + **100–200-word explanation** sourced from the text.

* **PPTX**

  * 2–3 slides per concept: idea → equation/relationship → small example.
  * Kid-friendly wording but faithful to the paper.
 
* **LAB**

  * 2–3 Exercise code Python. If you have no prior knowledge of programming skills, don't worry about that.
  * The exercise can show you how to running basicly and very friendly

* **XLSX**

  * Template sheets: `Overview`, `Results`, `Models/Params` (adjust as needed).
  * Uses consistent column names for easy multi-paper comparison.

---

## 📂 Suggested Repo Structure

```
.
├─ app/                 # TypeScript UI
├─ orchestrator/        # prompt runners, guards, templates
├─ exporters/
│  ├─ docx/
│  ├─ pptx/
│  ├─ lab/
│  └─ xlsx/
├─ parsers/             # pdf/text/figure utilities (optional python/)
├─ prompts/             # summary/slides/results templates
├─ inputs/              # drop PDFs here
├─ outputs/             # generated files
├─ .env.example
└─ README.md
```

---

## 🔒 Data & Reliability

* No invented numbers/claims; extractions only from the provided PDF.
* Equations kept intact; metric names and symbols are not rewritten.
* Runs locally; you control API keys and files.

---

## 🛣️ Roadmap

* [ ] **RAG** for smarter context windows
* [ ] **Multi-document compare** (20+ PDFs)
* [ ] Batch mode & CLI
* [ ] More export templates (Notion/CSV/Markdown)

---

## 🤝 Contributing

PRs and issues are welcome!
Please include a minimal PDF sample, expected outputs, and which template you used.

---

## 📄 License
---

## 👤 Maintainer

** Jericho/ essor1234** — Computer Science - Computer Vision & AI Engineer
Focus: detection/segmentation, equation-safe extraction, and edge-friendly tooling.

---

### Quick Links

* Repo: `https://github.com/essor1234/-Project-Rias_Assistant`
* Issues: `https://github.com/essor1234/-Project-Rias_Assistant/issues`

---

Need me to tailor the README to your exact folders/scripts (e.g., `npm run build:docx`, `python parsers/figure_map.py`)? Drop the file list or a screenshot of your repo tree and I’ll align the commands verbatim.
