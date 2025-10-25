# suggest_papers.py
import json
import sys
import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
import time
from openpyxl import Workbook

# ----------------------------------------------------------------------
# LOGGING SETUP — print to both console AND file
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
LOG_FILE = LOG_DIR / f"suggest_papers_log_{timestamp}.txt"
log_f = open(LOG_FILE, "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, log_f)
sys.stderr = Tee(sys.__stderr__, log_f)
# ----------------------------------------------------------------------

load_dotenv()

# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------
TXT_DIR = SCRIPT_DIR / "data" / "extracted_text" / "testing_files"  # Folder containing input .txt files
PROMPT_PATH = SCRIPT_DIR / "prompts" / "[Prompt]suggest_papers.txt"

MODEL = "gpt-4o"
MAX_TOKENS = 2500
TEMPERATURE = 0.4
MAX_RETRIES = 3

OUTPUT_XLSX = SCRIPT_DIR / "data\suggest_paper_output/suggested_papers.xlsx"
# ----------------------------------------------------------------------

def format_for_excel(value):
    """Convert lists or dicts into readable strings for Excel."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    elif isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    else:
        return value


def truncate_text(text: str, limit: int = 20_000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\n[Text truncated for LLM]"


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def call_llm(prompt_text: str) -> str:
    """Send text to GPT-4o and expect JSON."""
    client = OpenAI()
    messages = [
        {"role": "system", "content": "You are an academic research assistant. Return only valid JSON."},
        {"role": "user", "content": prompt_text},
    ]

    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
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


def clean_raw(raw: str) -> str:
    """Remove markdown fences or JSON prefixes."""
    if raw.startswith("```"):
        parts = raw.split("```", 2)
        raw = parts[1] if len(parts) > 2 else parts[0]
    raw = raw.strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    return raw


def main():
    print("\n--- Starting paper suggestion process ---")
    txt_files = sorted(TXT_DIR.glob("*.txt"))
    if not txt_files:
        print("❌ No .txt files found in:", TXT_DIR)
        return

    base_prompt = load_prompt()
    all_suggestions = []

    for txt_path in txt_files:
        print(f"\n📄 Processing {txt_path.name}")
        full_text = txt_path.read_text(encoding="utf-8")
        combined_prompt = base_prompt.replace("<<<DOCUMENT_TEXT>>>", truncate_text(full_text))

        raw = call_llm(combined_prompt)
        cleaned = clean_raw(raw)

        try:
            data = json.loads(cleaned)
            suggestions = data.get("Suggestions", [])
            for s in suggestions:
                s["Source File"] = txt_path.name
            all_suggestions.extend(suggestions)
            print(f"✅ {len(suggestions)} suggestions found for {txt_path.name}")

        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error for {txt_path.name}: {e}")
            continue

    if not all_suggestions:
        print("⚠️ No suggestions found.")
        return

    df = pd.DataFrame(all_suggestions)
    cols = ["Source File", "File Name", "Author", "Summary Information", "Keywords", "Reference Link"]
    df = df[[c for c in cols if c in df.columns]]

    # Save to Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Suggested Papers"
    ws.append(cols)
    for _, row in df.iterrows():
        ws.append([format_for_excel(row.get(c, "")) for c in cols])
    wb.save(OUTPUT_XLSX)

    print(f"\n💾 Suggested papers saved to: {OUTPUT_XLSX}")
    print(f"🪵 Log saved at: {LOG_FILE}")


if __name__ == "__main__":
    main()
