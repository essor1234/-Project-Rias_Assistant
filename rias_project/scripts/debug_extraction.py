#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import datetime
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
class Tee:
    def __init__(self, *files): self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj); f.flush()
    def flush(self):
        for f in self.files: f.flush()

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
SCRIPT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"summary_log_{timestamp}.txt"
log_f = open(LOG_FILE, "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, log_f)
sys.stderr = Tee(sys.__stderr__, log_f)

load_dotenv()
client = OpenAI()

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
TXT_DIR      = SCRIPT_DIR / "data" / "extracted_text" / "test4"
IMAGES_DIR   = SCRIPT_DIR / "data" / "extracted_image" / "test4"
PROMPT_PATH  = SCRIPT_DIR / "prompts" / "[Prompt]summarize_papers.txt"
MODEL        = "gpt-4o"
MAX_TOKENS   = 8000
TEMPERATURE  = 0.2
MAX_RETRIES  = 3

OUTPUT_DIR   = SCRIPT_DIR / "data" / "summarize_to_doc_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DOCX  = OUTPUT_DIR / "Paper_Summary_Matched.docx"

# ---------------------------------------------------------------------
# Helper: truncate long texts for the LLM
# ---------------------------------------------------------------------
def truncate_text(text: str, limit: int = 40_000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n[Text truncated for LLM]"

# ---------------------------------------------------------------------
# Load prompt template
# ---------------------------------------------------------------------
def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")

# ---------------------------------------------------------------------
# LLM call with exponential back-off
# ---------------------------------------------------------------------
def call_llm(prompt: str) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a precise academic summarizer and document restorer."},
                    {"role": "user",   "content": prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"Attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    return ""

# ---------------------------------------------------------------------
# Clean LLM output (remove fences, json prefix)
# ---------------------------------------------------------------------
def clean_raw(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 1)[1].rsplit("```", 1)[0]
    if raw.lower().startswith("json"):
        raw = raw[4:].lstrip()
    return raw.strip()

# ---------------------------------------------------------------------
# Insert image + caption (centered, caption italic, proper spacing)
# ---------------------------------------------------------------------
def insert_image(doc: Document, img_path: Path, caption: str):
    try:
        # ---- Image ----
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_img.add_run()
        run.add_picture(str(img_path), width=Inches(5.5))

        # ---- Caption ----
        p_cap = doc.add_paragraph(caption, style="Caption")
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # Make caption italic
        for run_cap in p_cap.runs:
            run_cap.italic = True

        # Add a tiny vertical space after caption
        doc.add_paragraph()
    except Exception as e:
        print(f"Could not insert image {img_path.name}: {e}")

# ---------------------------------------------------------------------
# Custom style for captions (if not present)
# ---------------------------------------------------------------------
def ensure_caption_style(doc: Document):
    if "Caption" not in doc.styles:
        style = doc.styles.add_style("Caption", 1)  # WD_STYLE_TYPE.PARAGRAPH
        style.font.name = "Times New Roman"
        style.font.size = Pt(10)
        style.font.italic = True
        style.paragraph_format.space_after = Pt(6)

# ---------------------------------------------------------------------
# Build DOCX from LLM output
# ---------------------------------------------------------------------
def create_docx(summary_text: str, output_path: Path, images_dir: Path):
    doc = Document()
    # Global font
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)

    ensure_caption_style(doc)

    # Pre-load all images (case-insensitive)
    image_map = {p.name.lower(): p for p in images_dir.iterdir()
                 if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".bmp", ".svg"}}

    print(f"Found {len(image_map)} images in {images_dir}")

    # Split by double newlines – preserves empty lines inside blocks
    blocks = [b.strip() for b in summary_text.split("\n\n") if b.strip()]

    for block in blocks:
        line = block.strip()

        # ---------- Headings ----------
        if line.startswith("###"):
            doc.add_heading(line.lstrip("# ").strip(), level=3)
        elif line.startswith("##"):
            doc.add_heading(line.lstrip("# ").strip(), level=2)
        elif line.startswith("#"):
            doc.add_heading(line.lstrip("# ").strip(), level=1)

        # ---------- Figure placeholder ----------
        elif line.startswith("[[FIGURE:"):
            try:
                inner = line.strip("[]").replace("FIGURE:", "").strip()
                parts = [p.strip() for p in inner.split("|")]
                filename = parts[0]
                caption  = " | ".join(parts[1:])   # keep original separators for readability

                img_key = Path(filename).name.lower()
                if img_key in image_map:
                    insert_image(doc, image_map[img_key], caption)
                    print(f"Inserted image: {filename}")
                else:
                    print(f"Image NOT FOUND: {filename}")
                    p = doc.add_paragraph(f"[Image missing: {filename}] {caption}", style="Normal")
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                print(f"Figure parsing error: {e}\n   Block: {line}")
                doc.add_paragraph(line, style="Normal")

        # ---------- Equations (center) ----------
        elif any(op in line for op in ("=", "Σ", "∑", "∫", "α", "β", "γ", "θ", "λ")) and line.count("=") == 1:
            p = doc.add_paragraph(line, style="Normal")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # ---------- Tables (preserve markdown tables) ----------
        elif line.startswith("|") and "|---" in line:
            # Very simple markdown table → Word table
            rows = [r.strip() for r in block.splitlines() if r.strip()]
            if not rows: continue
            col_count = len(rows[0].split("|")) - 2  # ignore leading/trailing |
            table = doc.add_table(rows=0, cols=col_count)
            table.style = "Table Grid"
            for i, row_text in enumerate(rows):
                cells = [c.strip() for c in row_text.split("|")[1:-1]]
                row_cells = table.add_row().cells
                for j, cell_text in enumerate(cells):
                    row_cells[j].text = cell_text
            doc.add_paragraph()  # spacing

        # ---------- Normal paragraph ----------
        else:
            doc.add_paragraph(line, style="Normal")

    doc.save(output_path)
    print(f"DOCX saved → {output_path}")

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main():
    print("\n=== Summarization with Images ===")
    base_prompt = load_prompt()

    txt_files = sorted(TXT_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files in {TXT_DIR}")
        return

    combined = "\n\n".join(
        f"--- FILE: {f.name} ---\n{truncate_text(f.read_text(encoding='utf-8'))}"
        for f in txt_files
    )
    prompt = base_prompt.replace("<<<DOCUMENT_TEXT>>>", combined)

    print(f"Calling LLM ({MODEL}) …")
    raw = call_llm(prompt)
    cleaned = clean_raw(raw)

    try:
        data = json.loads(cleaned)
        summary = data.get("SummaryDoc", "").strip()
        if not summary:
            print("LLM returned empty SummaryDoc.")
            return
        create_docx(summary, OUTPUT_DOCX, IMAGES_DIR)
    except json.JSONDecodeError as e:
        print("JSON decode failed:")
        print(e)
        print("\n--- RAW LLM OUTPUT (first 1500 chars) ---")
        print(cleaned[:1500])
        return

    print("\nAll done!")
    print(f"Log: {LOG_FILE}")

if __name__ == "__main__":
    main()