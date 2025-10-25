


import json
import sys
import datetime
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
from openpyxl import load_workbook


# ----------------------------------------------------------------------
# Utility: Dual output logging (console + file)
# ----------------------------------------------------------------------
class Tee:
    """Redirect stdout/stderr to both terminal and a log file."""

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
# Core class
# ----------------------------------------------------------------------
class DocsExcelGenerator:
    """
    Generates structured Excel reports from LLM analysis of text files
    (each text extracted from a research paper).
    """

    def __init__(
        self,
        txt_dir: Path,
        prompt_path: Path,
        template_path: Path,
        output_dir: Path,
        model: str = "gpt-4o",
        max_tokens: int = 2000,
        temperature: float = 0.0,
        max_retries: int = 3,
    ):
        load_dotenv()

        self.txt_dir = Path(txt_dir)
        self.prompt_path = Path(prompt_path)
        self.template_path = Path(template_path)
        self.output_dir = Path(output_dir)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_xlsx = self.output_dir / "comparison_output.xlsx"

        # Setup log
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_dir = self.output_dir.parent / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"debug_output_{timestamp}.txt"
        self._init_logging()

        print(f"📄 Logs will be saved to: {self.log_file}")

    # ------------------------------------------------------------------
    # Logging setup
    # ------------------------------------------------------------------
    def _init_logging(self):
        """Redirect stdout/stderr to both terminal and a log file."""
        log_f = open(self.log_file, "w", encoding="utf-8")
        sys.stdout = Tee(sys.__stdout__, log_f)
        sys.stderr = Tee(sys.__stderr__, log_f)

    # ------------------------------------------------------------------
    # Utility functions
    # ------------------------------------------------------------------
    @staticmethod
    def truncate_text(text: str, limit: int = 25_000) -> str:
        return text if len(text) <= limit else text[:limit] + "\n\n[Text truncated for LLM]"

    def load_prompt(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8")

    @staticmethod
    def clean_raw(raw: str) -> str:
        if raw.startswith("```"):
            parts = raw.split("```", 2)
            raw = parts[1] if len(parts) > 2 else parts[0]
        raw = raw.strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        return raw

    # ------------------------------------------------------------------
    # LLM communication
    # ------------------------------------------------------------------
    def call_llm(self, prompt_text: str) -> str:
        """Send prompt to OpenAI model and return response."""
        client = OpenAI()
        messages = [
            {
                "role": "system",
                "content": "You are a research paper analyst. Return ONLY valid JSON following the given schema.",
            },
            {"role": "user", "content": prompt_text},
        ]

        for attempt in range(self.max_retries):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                print(f"⚠️ Attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
        return ""

    # ------------------------------------------------------------------
    # Process a single text file
    # ------------------------------------------------------------------
    def process_single_paper(self, txt_path: Path, paper_id: str, prompt_base: str):
        """Run LLM extraction for one paper and return two DataFrames."""
        print(f"\n📘 Processing {txt_path.name} ({paper_id})")
        full_text = txt_path.read_text(encoding="utf-8")
        combined_prompt = prompt_base.replace("<<<DOCUMENT_TEXT>>>", self.truncate_text(full_text))

        raw = self.call_llm(combined_prompt)
        cleaned = self.clean_raw(raw)

        try:
            data = json.loads(cleaned)
            print(f"✅ JSON parsed successfully for {txt_path.name}")

            overview_df = pd.DataFrame(data.get("Overview", []))
            results_df = pd.DataFrame(data.get("Results", []))

            if not overview_df.empty:
                overview_df["PaperID"] = paper_id
            if not results_df.empty:
                results_df["PaperID"] = paper_id

            return overview_df, results_df

        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed for {txt_path.name}: {e}")
            return pd.DataFrame(), pd.DataFrame()

    # ------------------------------------------------------------------
    # Write to Excel template
    # ------------------------------------------------------------------
    def write_to_template(self, overview_df: pd.DataFrame, results_df: pd.DataFrame):
        """Insert dataframes into Excel template and save."""
        print("\n🧾 Writing all results to Excel template...")
        wb = load_workbook(self.template_path)

        if "Overview" in wb.sheetnames:
            ws = wb["Overview"]
            headers = [cell.value for cell in ws[1]]
            ws.delete_rows(2, ws.max_row)
            for _, row in overview_df.iterrows():
                ws.append([row.get(h, "") for h in headers])
            print(f"✅ Overview sheet updated with {len(overview_df)} entries")

        if "Results" in wb.sheetnames:
            ws = wb["Results"]
            headers = [cell.value for cell in ws[1]]
            ws.delete_rows(2, ws.max_row)
            for _, row in results_df.iterrows():
                ws.append([row.get(h, "") for h in headers])
            print(f"✅ Results sheet updated with {len(results_df)} entries")

        wb.save(self.output_xlsx)
        print(f"💾 Excel file saved to: {self.output_xlsx}")

    # ------------------------------------------------------------------
    # Main process
    # ------------------------------------------------------------------
    def run(self):
        """Run full multi-paper extraction pipeline."""
        print("\n🚀 Starting multi-paper extraction...")

        txt_files = sorted(self.txt_dir.glob("*.txt"))
        if not txt_files:
            print(f"❌ No .txt files found in {self.txt_dir}")
            return

        prompt_base = self.load_prompt()
        all_overview, all_results = [], []

        for i, txt_path in enumerate(txt_files, start=1):
            paper_id = f"P{i:02d}"
            overview_df, results_df = self.process_single_paper(txt_path, paper_id, prompt_base)
            if not overview_df.empty:
                all_overview.append(overview_df)
            if not results_df.empty:
                all_results.append(results_df)

        if not all_overview and not all_results:
            print("⚠️ No valid data extracted from any paper.")
            return

        combined_overview = pd.concat(all_overview, ignore_index=True) if all_overview else pd.DataFrame()
        combined_results = pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()

        self.write_to_template(combined_overview, combined_results)
        print("\n✅ All papers processed successfully!")
        print(f"🪵 Log file saved at: {self.log_file}")

#----------------------------------------------------------------------#
# # debug_extraction.py
# import json
# import sys
# import datetime
# from pathlib import Path
# from dotenv import load_dotenv
# from openai import OpenAI
# import pandas as pd
# import time
# from openpyxl import load_workbook

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
# LOG_FILE = LOG_DIR / f"debug_output_{timestamp}.txt"
# log_f = open(LOG_FILE, "w", encoding="utf-8")
# sys.stdout = Tee(sys.__stdout__, log_f)
# sys.stderr = Tee(sys.__stderr__, log_f)
# # ----------------------------------------------------------------------

# load_dotenv()

# # ----------------------------------------------------------------------
# # CONFIGURATION
# # ----------------------------------------------------------------------
# TXT_DIR = SCRIPT_DIR / "data" / "extracted_text" / "testing_files"       # Folder containing one or more .txt files
# PROMPT_PATH = SCRIPT_DIR / "prompts" / "prompt_compare_testing.txt"
# TEMPLATE_PATH = SCRIPT_DIR / "templates" / "Paper_Comparison_Template.xlsx"

# MODEL = "gpt-4o"
# MAX_TOKENS = 2000
# TEMPERATURE = 0.0
# MAX_RETRIES = 3

# # Change the output directory to comparisons folder
# OUTPUT_DIR = SCRIPT_DIR / "data" / "comparisons"
# OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# OUTPUT_XLSX = OUTPUT_DIR / "testing_comparison2.xlsx"
# # ----------------------------------------------------------------------


# def truncate_text(text: str, limit: int = 25_000) -> str:
#     return text if len(text) <= limit else text[:limit] + "\n\n[Text truncated for LLM]"


# def load_prompt() -> str:
#     return PROMPT_PATH.read_text(encoding="utf-8")


# def call_llm(prompt_text: str) -> str:
#     """Send text to GPT with prompt instructions."""
#     client = OpenAI()
#     messages = [
#         {"role": "system", "content": "You are a research paper analyst. Return ONLY valid JSON following the given schema."},
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
#             print(f"Attempt {attempt + 1} failed: {e}")
#             if attempt == MAX_RETRIES - 1:
#                 raise
#             time.sleep(2 ** attempt)
#     return ""


# def clean_raw(raw: str) -> str:
#     if raw.startswith("```"):
#         parts = raw.split("```", 2)
#         raw = parts[1] if len(parts) > 2 else parts[0]
#     raw = raw.strip()
#     if raw.lower().startswith("json"):
#         raw = raw[4:].strip()
#     return raw


# def write_to_template(template_path: Path, overview_df: pd.DataFrame, results_df: pd.DataFrame, output_path: Path):
#     """Insert combined data into a copy of the Excel template, preserving formatting."""
#     print("\n📘 Writing all results to Excel template...")
#     wb = load_workbook(template_path)

#     # ---- Write Overview ----
#     if "Overview" in wb.sheetnames:
#         ws = wb["Overview"]
#         headers = [cell.value for cell in ws[1]]
#         ws.delete_rows(2, ws.max_row)
#         for _, row in overview_df.iterrows():
#             ws.append([row.get(h, "") for h in headers])
#         print(f"✅ Overview sheet updated with {len(overview_df)} entries")

#     # ---- Write Results ----
#     if "Results" in wb.sheetnames:
#         ws = wb["Results"]
#         headers = [cell.value for cell in ws[1]]
#         ws.delete_rows(2, ws.max_row)
#         for _, row in results_df.iterrows():
#             ws.append([row.get(h, "") for h in headers])
#         print(f"✅ Results sheet updated with {len(results_df)} entries")

#     wb.save(output_path)
#     print(f"💾 Excel file saved to: {output_path}")


# def process_single_paper(txt_path: Path, paper_id: str, prompt_base: str):
#     """Run extraction for one paper and return Overview/Results DataFrames."""
#     print(f"\n--- Processing {txt_path.name} ({paper_id}) ---")
#     full_text = txt_path.read_text(encoding="utf-8")
#     combined_prompt = prompt_base.replace("<<<DOCUMENT_TEXT>>>", truncate_text(full_text))

#     raw = call_llm(combined_prompt)
#     cleaned = clean_raw(raw)

#     try:
#         data = json.loads(cleaned)
#         print(f"✅ JSON parsed successfully for {txt_path.name}")
#         overview_df = pd.DataFrame(data.get("Overview", []))
#         results_df = pd.DataFrame(data.get("Results", []))

#         # Assign PaperID if missing
#         if not overview_df.empty:
#             overview_df["PaperID"] = paper_id
#         if not results_df.empty:
#             results_df["PaperID"] = paper_id

#         return overview_df, results_df

#     except json.JSONDecodeError as e:
#         print(f"❌ JSON parsing failed for {txt_path.name}: {e}")
#         return pd.DataFrame(), pd.DataFrame()


# def main():
#     print("\n--- Starting multi-paper extraction ---")

#     txt_files = sorted(TXT_DIR.glob("*.txt"))
#     if not txt_files:
#         print("❌ No .txt files found in directory:", TXT_DIR)
#         return

#     prompt_base = load_prompt()

#     all_overview = []
#     all_results = []

#     for i, txt_path in enumerate(txt_files, start=1):
#         paper_id = f"P{i:02d}"
#         overview_df, results_df = process_single_paper(txt_path, paper_id, prompt_base)
#         if not overview_df.empty:
#             all_overview.append(overview_df)
#         if not results_df.empty:
#             all_results.append(results_df)

#     if not all_overview and not all_results:
#         print("⚠️ No valid data extracted from any paper.")
#         return

#     combined_overview = pd.concat(all_overview, ignore_index=True) if all_overview else pd.DataFrame()
#     combined_results = pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()

#     write_to_template(TEMPLATE_PATH, combined_overview, combined_results, OUTPUT_XLSX)
#     print("\n✅ All papers processed successfully!")


# if __name__ == "__main__":
#     main()
#     print("\n--- Script finished ---")
#     print(f"Log file saved at: {LOG_FILE}")
