# generate_edu_materials.py
import json
import sys
import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import time
import pandas as pd
from pptx import Presentation
from pptx.util import Inches
from zipfile import ZipFile

# ----------------------------------------------------------------------
# LOGGING SETUP — print to both console and log file
# ----------------------------------------------------------------------
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
LOG_FILE = LOG_DIR / f"edu_materials_log_{timestamp}.txt"
log_f = open(LOG_FILE, "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, log_f)
sys.stderr = Tee(sys.__stderr__, log_f)
# ----------------------------------------------------------------------

load_dotenv()
client = OpenAI()

# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------
TXT_DIR = SCRIPT_DIR / "data" / "extracted_text" / "test4"
PROMPT_PATH = SCRIPT_DIR / "prompts" / "[Prompt]explain_and_lab.txt"
MODEL = "gpt-4o"
MAX_TOKENS = 4000
TEMPERATURE = 0.0
MAX_RETRIES = 3
# ----------------------------------------------------------------------


def truncate_text(text, limit=20_000):
    return text if len(text) <= limit else text[:limit] + "\n\n[Text truncated for LLM]"


def load_prompt():
    return PROMPT_PATH.read_text(encoding="utf-8")


def call_llm(prompt_text):
    """Call GPT-4o with retries"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an educational AI tutor that outputs structured JSON only. "
                            "If the paper has few metrics, you may generate example metrics for teaching, "
                            "but keep consistent JSON keys. "
                            "Never output markdown or commentary — JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt_text},
                ],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
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
    if not raw:
        return ""
    if raw.startswith("```"):
        parts = raw.split("```", 2)
        raw = parts[1] if len(parts) > 2 else parts[0]
    raw = raw.strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    return raw


# ----------------------------------------------------------------------
# PowerPoint Writer (robust)
# ----------------------------------------------------------------------
def create_ppt(slides, output_path, raw_json_sample=None):
    """
    Create a clean PPTX with real content.
    If 'Content' field missing, combine Equation + Explanation + Example.
    """
    prs = Presentation()
    for slide in slides:
        layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
        s = prs.slides.add_slide(layout)

        # Title
        title = slide.get("Title") or slide.get("Heading") or "Untitled"
        try:
            s.shapes.title.text = str(title)
        except Exception:
            pass

        # Compose content
        if slide.get("Content"):
            content_text = slide.get("Content")
        else:
            parts = []
            for k in ("Equation", "ConceptExplanation", "DeepExplanation", "RealExample", "ImageIdea"):
                v = slide.get(k)
                if v:
                    parts.append(f"{k}: {v}")
            content_text = "\n\n".join(parts) if parts else ""

        # Find a text placeholder (not title)
        body_shape = None
        for shape in s.shapes:
            if hasattr(shape, "text_frame") and shape != s.shapes.title:
                body_shape = shape
                break

        if body_shape is None:
            # fallback: new text box
            left, top, width, height = Inches(0.5), Inches(1.5), Inches(9), Inches(4.5)
            body_shape = s.shapes.add_textbox(left, top, width, height)

        body_shape.text_frame.clear()
        content_text = content_text[:4000] or "No detailed content available."
        p = body_shape.text_frame.paragraphs[0]
        p.text = content_text

    prs.save(output_path)
    print(f"📊 Slides saved to {output_path}")

    # Save raw JSON alongside
    if raw_json_sample:
        raw_path = Path(output_path).with_suffix(".raw.json")
        raw_path.write_text(json.dumps(raw_json_sample, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"🔎 Raw JSON saved to {raw_path}")


# ----------------------------------------------------------------------
# ZIP Generator for Labs
# ----------------------------------------------------------------------
def create_lab_zip(labs, output_zip_path):
    """Generate zip with datasets + python templates."""
    if not labs:
        print("⚠️ No labs to package.")
        return

    with ZipFile(output_zip_path, "w") as zf:
        for i, lab in enumerate(labs, start=1):
            title = lab.get("Title", f"Lab_{i}")
            dataset = lab.get("Dataset", {})
            codefiles = lab.get("CodeFiles", [])

            # CSV file
            if dataset:
                csv_name = dataset.get("filename", f"{title.replace(' ', '_')}.csv")
                csv_content = "x,y,true_label,pred_label\n1,0.8,1,1\n2,0.3,1,0\n3,0.9,0,1\n"
                zf.writestr(csv_name, csv_content)
                readme = f"# Dataset: {csv_name}\n\n{dataset.get('description', '')}\n"
                zf.writestr(f"{title}_README.txt", readme)

            # Python files
            for j, cfile in enumerate(codefiles, start=1):
                name = cfile.get("filename", f"exercise_{i}_{j}.py")
                desc = cfile.get("description", "")
                code_content = (
                    f"# {desc}\n"
                    f"import pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\n\n"
                    f"data = pd.read_csv('{dataset.get('filename','data.csv')}')\n"
                    f"print(data.head())\n"
                )
                zf.writestr(name, code_content)

    print(f"🧩 Lab files saved to {output_zip_path}")


# ----------------------------------------------------------------------
# Main Processing
# ----------------------------------------------------------------------
def process_paper(txt_path, base_prompt, edu_output):
    print(f"\n📘 Processing {txt_path.name}")
    text = truncate_text(txt_path.read_text(encoding="utf-8"))
    combined = base_prompt.replace("<<<DOCUMENT_TEXT>>>", text)

    raw = call_llm(combined)
    cleaned = clean_raw(raw)

    if not cleaned:
        print("⚠️ No response from GPT.")
        return [], []

    debug_raw_path = edu_output / f"{txt_path.stem}_raw.txt"
    debug_raw_path.write_text(cleaned, encoding="utf-8")

    try:
        data = json.loads(cleaned)
        slides = data.get("Slides", [])
        labs = data.get("Labs", [])
        print(f"✅ Parsed JSON: {len(slides)} slides, {len(labs)} labs")
        return slides, labs, data
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error for {txt_path.name}: {e}")
        print("Raw output sample:", cleaned[:1000])
        return [], [], {}


def main():
    print("\n--- Generating educational materials ---")
    prompt = load_prompt()
    txt_files = sorted(TXT_DIR.glob("*.txt"))
    if not txt_files:
        print("❌ No .txt files found")
        return

    edu_output = SCRIPT_DIR / "data" / "edu_output"
    edu_output.mkdir(parents=True, exist_ok=True)

    for txt_path in txt_files:
        slides, labs, data = process_paper(txt_path, prompt, edu_output)
        if not slides and not labs:
            print(f"⚠️ No educational content generated for {txt_path.name}")
            continue

        out_ppt = edu_output / f"slides_{txt_path.stem}.pptx"
        out_zip = edu_output / f"lab_{txt_path.stem}.zip"

        if slides:
            create_ppt(slides, out_ppt, raw_json_sample=data)
        if labs:
            create_lab_zip(labs, out_zip)

    print("\n✅ All papers processed successfully!")
    print(f"Log file saved at: {LOG_FILE}")


if __name__ == "__main__":
    main()
