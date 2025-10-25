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
from pptx.util import Inches, Pt
from zipfile import ZipFile
import io

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
MAX_TOKENS = 2500
TEMPERATURE = 0.4
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
                    {"role": "system", "content": "You are an educational AI tutor."},
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
    if raw.startswith("```"):
        parts = raw.split("```", 2)
        raw = parts[1] if len(parts) > 2 else parts[0]
    raw = raw.strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    return raw


def create_ppt(slides, output_path):
    prs = Presentation()
    for slide in slides:
        slide_layout = prs.slide_layouts[1]
        s = prs.slides.add_slide(slide_layout)
        s.shapes.title.text = slide.get("Title", "")
        s.placeholders[1].text = slide.get("Content", "")
    prs.save(output_path)
    print(f"📊 Slides saved to {output_path}")


def create_lab_zip(exercises, output_zip_path):
    """Generate zip file with dataset and python files"""
    with ZipFile(output_zip_path, "w") as zf:
        for ex in exercises:
            dataset = ex.get("Dataset", {})
            codefiles = ex.get("CodeFiles", [])

            if dataset:
                csv_name = dataset.get("filename", "data.csv")
                csv_content = "x,y\n1,2\n2,4\n3,6\n"
                zf.writestr(csv_name, csv_content)
                readme = f"# Dataset: {csv_name}\n\n{dataset.get('description', '')}\n"
                zf.writestr("README_DATA.txt", readme)

            for cfile in codefiles:
                name = cfile.get("filename", "exercise.py")
                desc = cfile.get("description", "")
                code_content = f"# {desc}\n\nimport pandas as pd\n\ndata = pd.read_csv('toy_data.csv')\nprint(data.head())"
                zf.writestr(name, code_content)
        print(f"🧩 Lab files saved to {output_zip_path}")


def process_paper(txt_path, base_prompt):
    print(f"\n📘 Processing {txt_path.name}")
    text = truncate_text(txt_path.read_text(encoding="utf-8"))
    combined = base_prompt.replace("<<<DOCUMENT_TEXT>>>", text)
    raw = call_llm(combined)
    cleaned = clean_raw(raw)

    try:
        data = json.loads(cleaned)
        slides = data.get("Slides", [])
        exercises = data.get("Exercises", [])
        equations = data.get("Equations", [])
        return slides, equations, exercises
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error for {txt_path.name}: {e}")
        return [], [], []


def main():
    print("\n--- Generating educational materials ---")
    prompt = load_prompt()
    txt_files = sorted(TXT_DIR.glob("*.txt"))
    if not txt_files:
        print("❌ No .txt files found")
        return

    for txt_path in txt_files:
        slides, equations, exercises = process_paper(txt_path, prompt)
        if not slides:
            print(f"⚠️ No educational content generated for {txt_path.name}")
            continue

        out_ppt = TXT_DIR / f"slides_{txt_path.stem}.pptx"
        out_zip = TXT_DIR / f"lab_{txt_path.stem}.zip"

        create_ppt(slides, out_ppt)
        create_lab_zip(exercises, out_zip)

    print("\n✅ All papers processed successfully!")
    print(f"Log file saved at: {LOG_FILE}")


if __name__ == "__main__":
    main()
