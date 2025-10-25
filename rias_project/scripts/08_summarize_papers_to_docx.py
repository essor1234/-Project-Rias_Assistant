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

# ---------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------
class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
SCRIPT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"summary_log_{timestamp}.txt"
log_f = open(LOG_FILE, "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, log_f)
sys.stderr = Tee(sys.__stderr__, log_f)
# ---------------------------------------------------------------------

load_dotenv()
client = OpenAI()

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
TXT_DIR = SCRIPT_DIR / "data" / "extracted_text" / "test4"
IMAGES_DIR = SCRIPT_DIR / "data" / "extracted_image" / "test4" # Folder with images
PROMPT_PATH = SCRIPT_DIR / "prompts" / "[Prompt]summarize_papers.txt"
MODEL = "gpt-4o"
MAX_TOKENS = 8000
TEMPERATURE = 0.2
MAX_RETRIES = 3

OUTPUT_DIR = SCRIPT_DIR / "data" / "summarize_to_doc_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DOCX = OUTPUT_DIR / "Paper_Summary_Matched.docx"
# ---------------------------------------------------------------------


def truncate_text(text, limit=40_000):
    return text if len(text) <= limit else text[:limit] + "\n\n[Text truncated for LLM]"


def load_prompt():
    return PROMPT_PATH.read_text(encoding="utf-8")


def call_llm(prompt_text):
    """Send text to GPT and retry on failure."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a precise academic summarizer and document restorer."},
                    {"role": "user", "content": prompt_text},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    return ""


def clean_raw(raw):
    """Remove Markdown fences or 'json' prefixes."""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
    raw = raw.strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    return raw


def insert_image(doc, img_path, caption_text):
    """Insert an image + caption to the DOCX."""
    try:
        p = doc.add_paragraph()
        run = p.add_run()
        run.add_picture(str(img_path), width=Inches(5.5))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        caption = doc.add_paragraph(caption_text, style="Normal")
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption.runs[0].italic = True
    except Exception as e:
        print(f"⚠️ Could not insert image {img_path}: {e}")


def create_docx(summary_text, output_path, images_dir):
    """Write the structured summary to a formatted Word DOCX, inserting actual images."""
    doc = Document()
    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(12)

    image_files = {f.name.lower(): f for f in images_dir.glob("*") if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".bmp"]}

    sections = summary_text.split("\n\n")
    for para in sections:
        line = para.strip()

        # Headings
        if line.startswith("###"):
            doc.add_heading(line.strip("# ").strip(), level=3)
        elif line.startswith("##"):
            doc.add_heading(line.strip("# ").strip(), level=2)
        elif line.startswith("#"):
            doc.add_heading(line.strip("# ").strip(), level=1)

        # Figure placeholders
        elif line.startswith("[[FIGURE:"):
            try:
                # Parse figure placeholder
                inner = line.strip("[]").replace("FIGURE:", "").strip()
                parts = [p.strip() for p in inner.split("|")]
                filename = parts[0].strip()

                # Extract caption properly
                caption_text = ""
                for part in parts[1:]:
                    if part.startswith("Caption:"):
                        caption_text = part.split("Caption:", 1)[1].strip().strip('"')
                        break

                if not caption_text:
                    caption_text = " ".join(parts[1:])  # Fallback

                # match image by filename
                fname = Path(filename).name.lower()
                if fname in image_files:
                    insert_image(doc, image_files[fname], caption_text)
                else:
                    p = doc.add_paragraph(f"[Image missing: {filename}] {caption_text}", style="Normal")
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                print(f"⚠️ Error parsing figure line: {e}")
                doc.add_paragraph(line, style="Normal")

        # Equations
        elif "=" in line and any(sym in line for sym in ["=", "Σ", "∑", "∫"]):
            p = doc.add_paragraph(line, style="Normal")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Normal text
        else:
            doc.add_paragraph(line, style="Normal")

    doc.save(output_path)
    print(f"📘 DOCX saved to: {output_path}")


def main():
    print("\n--- Starting summarization with images ---")
    base_prompt = load_prompt()

    txt_files = sorted(TXT_DIR.glob("*.txt"))
    if not txt_files:
        print("❌ No .txt files found in:", TXT_DIR)
        return

    combined_text = "\n\n".join([f"--- FILE: {f.name} ---\n{truncate_text(f.read_text(encoding='utf-8'))}" for f in txt_files])

    # Add available image filenames to the input
    image_files = [f.name for f in IMAGES_DIR.glob("*") if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".bmp"]]
    image_list = "\n\nAvailable image filenames in the images folder (match these exactly for figures):\n" + ", ".join(image_files)

    prompt_filled = base_prompt.replace("<<<DOCUMENT_TEXT>>>", combined_text + image_list)

    print(f"Processing {len(txt_files)} text files and images from {IMAGES_DIR}...")
    raw = call_llm(prompt_filled)
    cleaned = clean_raw(raw)

    try:
        data = json.loads(cleaned)
        summary_text = data.get("SummaryDoc", "")
        if not summary_text.strip():
            print("⚠️ Empty summary output.")
            return
        create_docx(summary_text, OUTPUT_DOCX, IMAGES_DIR)
    except json.JSONDecodeError as e:
        print("❌ JSON parse error:", e)
        print(cleaned[:1000])

    print("\n✅ Summarization complete!")
    print(f"Log saved at: {LOG_FILE}")


if __name__ == "__main__":
    main()