import json
import sys
import time
import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
from openpyxl import Workbook


# ----------------------------------------------------------------------
# LOGGING HELPER
# ----------------------------------------------------------------------
class Tee:
    """Duplicates stdout/stderr output to both console and log file."""
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()

    def flush(self):
        for f in self.files:
            f.flush()


# ----------------------------------------------------------------------
# MAIN CLASS
# ----------------------------------------------------------------------
class PaperSuggester:
    """Suggests related research papers for extracted text files using GPT."""

    def __init__(self):
        load_dotenv()

        # --- Paths and logging setup ---
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.script_dir = Path(__file__).resolve().parent.parent
        self.log_dir = self.script_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"suggest_papers_log_{self.timestamp}.txt"

        # Redirect stdout/stderr to both console and log file
        self.log_f = open(self.log_file, "w", encoding="utf-8")
        sys.stdout = Tee(sys.__stdout__, self.log_f)
        sys.stderr = Tee(sys.__stderr__, self.log_f)

        # --- Configuration ---
        self.txt_dir = self.script_dir / "data" / "extracted_text" / "testing_files"
        self.prompt_path = self.script_dir / "prompts" / "[Prompt]suggest_papers.txt"
        self.output_xlsx = self.script_dir / "data" / "suggest_paper_output" / "suggested_papers.xlsx"
        self.output_xlsx.parent.mkdir(parents=True, exist_ok=True)

        # --- LLM settings ---
        self.model = "gpt-4o"
        self.max_tokens = 2500
        self.temperature = 0.4
        self.max_retries = 3
        self.client = OpenAI()

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------
    @staticmethod
    def truncate_text(text: str, limit: int = 20_000) -> str:
        """Truncate overly long text for model input."""
        return text if len(text) <= limit else text[:limit] + "\n\n[Text truncated for LLM]"

    @staticmethod
    def format_for_excel(value):
        """Ensure structured values (lists, dicts) are readable in Excel."""
        if isinstance(value, list):
            return ", ".join(map(str, value))
        elif isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return value

    def load_prompt(self) -> str:
        """Load the base prompt template."""
        return self.prompt_path.read_text(encoding="utf-8")

    @staticmethod
    def clean_raw(raw: str) -> str:
        """Strip Markdown code fences and JSON prefixes."""
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```", 2)
            raw = parts[1] if len(parts) > 1 else parts[0]
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        return raw

    # ------------------------------------------------------------------
    # LLM caller
    # ------------------------------------------------------------------
    def call_llm(self, prompt_text: str) -> str:
        """Send prompt to GPT and return raw JSON string."""
        messages = [
            {"role": "system", "content": "You are an academic research assistant. Return only valid JSON."},
            {"role": "user", "content": prompt_text},
        ]

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                print(f"⚠️ Attempt {attempt}/{self.max_retries} failed: {e}")
                if attempt == self.max_retries:
                    raise
                time.sleep(2 ** attempt)
        return ""

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------
    def process_txt_file(self, txt_path: Path, base_prompt: str):
        """Generate paper suggestions for a single text file."""
        print(f"\n📄 Processing {txt_path.name}")
        full_text = txt_path.read_text(encoding="utf-8")
        combined_prompt = base_prompt.replace("<<<DOCUMENT_TEXT>>>", self.truncate_text(full_text))

        raw = self.call_llm(combined_prompt)
        cleaned = self.clean_raw(raw)

        try:
            data = json.loads(cleaned)
            suggestions = data.get("Suggestions", [])
            for s in suggestions:
                s["Source File"] = txt_path.name
            print(f"✅ {len(suggestions)} suggestions found for {txt_path.name}")
            return suggestions
        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error for {txt_path.name}: {e}")
            return []

    def save_to_excel(self, suggestions: list):
        """Write suggestions to Excel with nice formatting."""
        if not suggestions:
            print("⚠️ No suggestions to save.")
            return

        df = pd.DataFrame(suggestions)
        columns = ["Source File", "File Name", "Author", "Summary Information", "Keywords", "Reference Link"]
        df = df[[c for c in columns if c in df.columns]]

        wb = Workbook()
        ws = wb.active
        ws.title = "Suggested Papers"
        ws.append(columns)

        for _, row in df.iterrows():
            ws.append([self.format_for_excel(row.get(c, "")) for c in columns])

        wb.save(self.output_xlsx)
        print(f"\n💾 Suggested papers saved to: {self.output_xlsx}")

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------
    def run(self):
        """Run the full suggestion pipeline."""
        print("\n🚀 Starting paper suggestion process...")
        txt_files = sorted(self.txt_dir.glob("*.txt"))
        if not txt_files:
            print(f"❌ No .txt files found in: {self.txt_dir}")
            return

        base_prompt = self.load_prompt()
        all_suggestions = []

        for txt_path in txt_files:
            suggestions = self.process_txt_file(txt_path, base_prompt)
            all_suggestions.extend(suggestions)

        self.save_to_excel(all_suggestions)
        print(f"🪵 Log saved at: {self.log_file}")
        print("✅ Process complete.")


# ----------------------------------------------------------------------
# Example entrypoint
# ----------------------------------------------------------------------
if __name__ == "__main__":
    suggester = PaperSuggester()
    suggester.run()


#------------------------------------------------------
# # suggest_papers.py
# import json
# import sys
# import datetime
# from pathlib import Path
# from dotenv import load_dotenv
# from openai import OpenAI
# import pandas as pd
# import time
# from openpyxl import Workbook

# # ----------------------------------------------------------------------
# # LOGGING SETUP — print to both console AND file
# # ----------------------------------------------------------------------
# class Tee:
#     def __init__(self, *files):
#         self.files = files
#     def write(self, obj):
#         for f in self.files:
#             f.write(obj)
#             f.flush()
#     def flush(self):
#         for f in self.files:
#             f.flush()

# timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
# SCRIPT_DIR = Path(__file__).resolve().parent.parent
# LOG_DIR = SCRIPT_DIR / "logs"
# LOG_DIR.mkdir(exist_ok=True)
# LOG_FILE = LOG_DIR / f"suggest_papers_log_{timestamp}.txt"
# log_f = open(LOG_FILE, "w", encoding="utf-8")
# sys.stdout = Tee(sys.__stdout__, log_f)
# sys.stderr = Tee(sys.__stderr__, log_f)
# # ----------------------------------------------------------------------

# load_dotenv()

# # ----------------------------------------------------------------------
# # CONFIGURATION
# # ----------------------------------------------------------------------
# TXT_DIR = SCRIPT_DIR / "data" / "extracted_text" / "testing_files"  # Folder containing input .txt files
# PROMPT_PATH = SCRIPT_DIR / "prompts" / "[Prompt]suggest_papers.txt"

# MODEL = "gpt-4o"
# MAX_TOKENS = 2500
# TEMPERATURE = 0.4
# MAX_RETRIES = 3

# OUTPUT_XLSX = SCRIPT_DIR / "data\suggest_paper_output/suggested_papers.xlsx"
# # ----------------------------------------------------------------------

# def format_for_excel(value):
#     """Convert lists or dicts into readable strings for Excel."""
#     if isinstance(value, list):
#         return ", ".join(str(v) for v in value)
#     elif isinstance(value, dict):
#         return json.dumps(value, ensure_ascii=False)
#     else:
#         return value


# def truncate_text(text: str, limit: int = 20_000) -> str:
#     return text if len(text) <= limit else text[:limit] + "\n\n[Text truncated for LLM]"


# def load_prompt() -> str:
#     return PROMPT_PATH.read_text(encoding="utf-8")


# def call_llm(prompt_text: str) -> str:
#     """Send text to GPT-4o and expect JSON."""
#     client = OpenAI()
#     messages = [
#         {"role": "system", "content": "You are an academic research assistant. Return only valid JSON."},
#         {"role": "user", "content": prompt_text},
#     ]

#     for attempt in range(MAX_RETRIES):
#         try:
#             resp = client.chat.completions.create(
#                 model=MODEL,
#                 messages=messages,
#                 max_tokens=MAX_TOKENS,
#                 temperature=TEMPERATURE,
#                 response_format={"type": "json_object"},
#             )
#             return resp.choices[0].message.content.strip()
#         except Exception as e:
#             print(f"Attempt {attempt+1} failed: {e}")
#             if attempt == MAX_RETRIES - 1:
#                 raise
#             time.sleep(2 ** attempt)
#     return ""


# def clean_raw(raw: str) -> str:
#     """Remove markdown fences or JSON prefixes."""
#     if raw.startswith("```"):
#         parts = raw.split("```", 2)
#         raw = parts[1] if len(parts) > 2 else parts[0]
#     raw = raw.strip()
#     if raw.lower().startswith("json"):
#         raw = raw[4:].strip()
#     return raw


# def main():
#     print("\n--- Starting paper suggestion process ---")
#     txt_files = sorted(TXT_DIR.glob("*.txt"))
#     if not txt_files:
#         print("❌ No .txt files found in:", TXT_DIR)
#         return

#     base_prompt = load_prompt()
#     all_suggestions = []

#     for txt_path in txt_files:
#         print(f"\n📄 Processing {txt_path.name}")
#         full_text = txt_path.read_text(encoding="utf-8")
#         combined_prompt = base_prompt.replace("<<<DOCUMENT_TEXT>>>", truncate_text(full_text))

#         raw = call_llm(combined_prompt)
#         cleaned = clean_raw(raw)

#         try:
#             data = json.loads(cleaned)
#             suggestions = data.get("Suggestions", [])
#             for s in suggestions:
#                 s["Source File"] = txt_path.name
#             all_suggestions.extend(suggestions)
#             print(f"✅ {len(suggestions)} suggestions found for {txt_path.name}")

#         except json.JSONDecodeError as e:
#             print(f"❌ JSON parse error for {txt_path.name}: {e}")
#             continue

#     if not all_suggestions:
#         print("⚠️ No suggestions found.")
#         return

#     df = pd.DataFrame(all_suggestions)
#     cols = ["Source File", "File Name", "Author", "Summary Information", "Keywords", "Reference Link"]
#     df = df[[c for c in cols if c in df.columns]]

#     # Save to Excel
#     wb = Workbook()
#     ws = wb.active
#     ws.title = "Suggested Papers"
#     ws.append(cols)
#     for _, row in df.iterrows():
#         ws.append([format_for_excel(row.get(c, "")) for c in cols])
#     wb.save(OUTPUT_XLSX)

#     print(f"\n💾 Suggested papers saved to: {OUTPUT_XLSX}")
#     print(f"🪵 Log saved at: {LOG_FILE}")


# if __name__ == "__main__":
#     main()
