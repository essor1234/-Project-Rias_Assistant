import json
import sys
import datetime
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
from openpyxl import load_workbook
import glob
import os # Import os for a more robust lock
import shutil

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
    Generates structured Excel reports from LLM analysis of text files.
    """

    def __init__(
        self,
        prompt_path: Path,
        template_path: Path,
        output_dir: Path,
        model: str = "gpt-4o",
        max_tokens: int = 2000,
        temperature: float = 0.0,
        max_retries: int = 3,
    ):
        load_dotenv()

        self.prompt_path = Path(prompt_path)
        self.template_path = Path(template_path)
        self.output_dir = Path(output_dir)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_xlsx = self.output_dir / "comparison_output.xlsx" # Default

        # Setup log
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        try:
            self.log_dir = self.output_dir.parent.parent.parent / "logs"
            if not self.log_dir.exists():
                self.log_dir = self.output_dir / "logs"
        except Exception:
             self.log_dir = self.output_dir / "logs"
             
        self.log_dir.mkdir(parents=True, exist_ok=True)
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
            # Find the first empty row instead of deleting
            next_row = ws.max_row + 1
            if ws["A2"].value is None:  # If first data row is empty
                next_row = 2
                
            # Append new data starting from next_row
            for _, row in overview_df.iterrows():
                ws.append([row.get(h, "") for h in headers])
            print(f"✅ Overview sheet updated with {len(overview_df)} entries")

        if "Results" in wb.sheetnames:
            ws = wb["Results"]
            headers = [cell.value for cell in ws[1]]
            # Find the first empty row instead of deleting
            next_row = ws.max_row + 1
            if ws["A2"].value is None:  # If first data row is empty
                next_row = 2
                
            # Append new data starting from next_row
            for _, row in results_df.iterrows():
                ws.append([row.get(h, "") for h in headers])
            print(f"✅ Results sheet updated with {len(results_df)} entries")

        wb.save(self.output_xlsx)
        print(f"💾 Excel file saved to: {self.output_xlsx}")

    # ------------------------------------------------------------------
    # New method to run the comparison on ALL files
    # ------------------------------------------------------------------
    def run_comparison(self, txt_files: list):
        """
        Processes a list of txt files and saves one combined Excel.
        """
        print(f"\n--- Starting multi-paper comparison for {len(txt_files)} files ---")
        
        prompt_base = self.load_prompt()
        all_overview, all_results = [], []

        for i, txt_path in enumerate(txt_files, start=1):
            paper_id = txt_path.stem # Use the file stem (e.g., 'test3') as the ID
            overview_df, results_df = self.process_single_paper(txt_path, paper_id, prompt_base)
            if not overview_df.empty: all_overview.append(overview_df)
            if not results_df.empty: all_results.append(results_df)
        
        if not all_overview and not all_results:
            print("⚠️ No valid data extracted from any paper.")
            # Still save an empty file for consistency
            self.write_to_template(pd.DataFrame(), pd.DataFrame())
            return

        combined_overview = pd.concat(all_overview, ignore_index=True) if all_overview else pd.DataFrame()
        combined_results = pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()

        self.write_to_template(combined_overview, combined_results)
        print("\n✅ All papers processed successfully!")


# ------------------------------------------------------------------
# Bridge function for main.py pipeline
# ------------------------------------------------------------------
def run(pdf_path, out_dir, prev=None):
    """Bridge function for main.py pipeline."""
    try:
        p = Path(pdf_path)
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Get paths
        SCRIPT_DIR = Path(__file__).resolve().parent.parent
        template_path = SCRIPT_DIR / "templates" / "Paper_Comparison_Template.xlsx"
        prompt_path = SCRIPT_DIR / "prompts" / "[Prompt]compare_prompt.txt"
        
        # Get text directory from previous stage
        txt_dir = out.parent.parent / "processed" / "01_extract_text_output"
        txt_files = sorted(txt_dir.glob("*.txt"))

        # Get or create session output directory for shared Excel file
        session_dir = out.parent.parent.parent / "session_outputs"
        session_dir.mkdir(parents=True, exist_ok=True)
        output_xlsx = session_dir / "03_comparison.xlsx"

        print(f"Step 03: {p.stem} acquired lock. Running comparison...")
        print(f"Step 03: Found {len(txt_files)} text files to compare.")
        for txt in txt_files:
            print(f"  - {txt.name}")

        # Initialize generator with the correct constructor args (prompt_path, template_path, output_dir)
        generator = DocsExcelGenerator(
            prompt_path=prompt_path,
            template_path=template_path,
            output_dir=session_dir
        )

        # Ensure the generator will save to the shared session XLSX
        generator.output_xlsx = output_xlsx

        # Run comparison for all available text files (append behavior is handled in write_to_template)
        generator.run_comparison(txt_files)

        print(f"Step 03: {p.stem} releasing lock.")
        return {
            "status": "success",
            "files": [output_xlsx.name],
            "summary": "comparison generated"
        }

    except Exception as e:
        print(f"ERROR in compare_papers: {e}")
        return {"status": "error", "error": str(e)}


