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

    def __init__(self, txt_dir: Path, prompt_path: Path, output_xlsx: Path):
        load_dotenv()

        # --- Paths and logging setup ---
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.script_dir = Path(__file__).resolve().parent.parent # For standalone mode

        # Setup log dir relative to output
        self.output_xlsx = output_xlsx
        self.output_xlsx.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Try to put logs in central 'logs' folder
            self.log_dir = self.output_xlsx.parent.parent.parent.parent / "logs"
            if not self.log_dir.exists():
                self.log_dir = self.output_xlsx.parent / "logs"
        except Exception:
            self.log_dir = self.output_xlsx.parent / "logs"
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"suggest_papers_log_{self.timestamp}.txt"

        # Redirect stdout/stderr to both console and log file
        self.log_f = open(self.log_file, "w", encoding="utf-8")
        sys.stdout = Tee(sys.__stdout__, self.log_f)
        sys.stderr = Tee(sys.__stderr__, self.log_f)

        # --- Configuration from args ---
        self.txt_dir = txt_dir
        self.prompt_path = prompt_path
        # self.output_xlsx is already set

        # --- LLM settings ---
        self.model = "gpt-4o"
        self.max_tokens = 10000
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
            # Still save an empty file so the pipeline step is "successful"
            wb = Workbook()
            ws = wb.active
            ws.title = "Suggested Papers"
            ws.append(["Source File", "File Name", "Author", "Summary Information", "Keywords", "Reference Link"])
            ws.append(["No suggestions found."])
            wb.save(self.output_xlsx)
            print(f"💾 Empty suggestions file saved to: {self.output_xlsx}")
            return

        df = pd.DataFrame(suggestions)
        columns = ["Source File", "File Name", "Author", "Summary Information", "Keywords", "Reference Link"]
        # Ensure all columns exist, even if empty
        for col in columns:
            if col not in df.columns:
                df[col] = ""
                
        df = df[columns] # Reorder

        wb = Workbook()
        ws = wb.active
        ws.title = "Suggested Papers"
        ws.append(columns)

        for _, row in df.iterrows():
            ws.append([self.format_for_excel(row.get(c, "")) for c in columns])

        wb.save(self.output_xlsx)
        print(f"\n💾 Suggested papers saved to: {self.output_xlsx}")

    # ------------------------------------------------------------------
    # Runner (for standalone use)
    # ------------------------------------------------------------------
    def run(self):
        """Main entry point for running the suggester in standalone mode."""
        try:
            print("\n--- Starting paper suggestion process (standalone) ---")
            txt_files = sorted(self.txt_dir.glob("*.txt"))
            if not txt_files:
                print("❌ No .txt files found in:", self.txt_dir)
                return

            base_prompt = self.load_prompt()
            all_suggestions = []

            for txt_path in txt_files:
                suggestions = self.process_txt_file(txt_path, base_prompt)
                all_suggestions.extend(suggestions)

            if not all_suggestions:
                print("⚠️ No suggestions found.")
            
            self.save_to_excel(all_suggestions)

        except Exception as e:
            print(f"ERROR: {e}")


# ----------------------------------------------------------------------
# Runner function for integration with main.py
# ----------------------------------------------------------------------
def run(pdf_path, out_dir, prev=None):
    """Bridge function for main.py pipeline."""
    try:
        p = Path(pdf_path)
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        # 1. Get paths
        processed_dir = out.parent
        txt_file = processed_dir / "01_extract_text_output" / f"{p.stem}.txt"

        SCRIPT_DIR = Path(__file__).resolve().parent
        PROJECT_ROOT = SCRIPT_DIR.parent
        prompt_path = PROJECT_ROOT / "prompts" / "[Prompt]suggest_papers.txt"
        
        output_file = out / f"{p.stem}_suggestions.xlsx"

        # 2. Check inputs
        if not txt_file.exists():
            raise FileNotFoundError(f"Input text file not found: {txt_file}")
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        print(f"\nInput paths for suggestions {p.stem}:")
        print(f"- Text file: {txt_file}")
        print(f"- Output file: {output_file}")

        # 3. Initialize Suggester
        suggester = PaperSuggester(
            txt_dir=txt_file.parent, # Pass the directory
            prompt_path=prompt_path,
            output_xlsx=output_file  # Pass the specific output file
        )

        # 4. Process the single paper
        base_prompt = suggester.load_prompt()
        suggestions = suggester.process_txt_file(txt_file, base_prompt)

        # 5. Save the results
        suggester.save_to_excel(suggestions)

        # 6. Return success
        return {
            "status": "success",
            "files": [output_file.name],
            "summary": "suggestions generated"
        }

    except Exception as e:
        import traceback
        print(f"ERROR in suggest_papers: {e}")
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


# ----------------------------------------------------------------------
# Example entrypoint
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # --- Example paths for direct testing ---
    print("Running PaperSuggester in standalone mode...")
    
    SCRIPT_DIR = Path(__file__).resolve().parent.parent 
    
    MOCK_TXT_DIR = SCRIPT_DIR / "data" / "extracted_text" / "testing_files"
    MOCK_PROMPT = SCRIPT_DIR / "prompts" / "[Prompt]suggest_papers.txt"
    MOCK_OUTPUT = SCRIPT_DIR / "data" / "suggest_paper_output" / "direct_test_suggestions.xlsx"
    
    try:
        suggester = PaperSuggester(
            txt_dir=MOCK_TXT_DIR,
            prompt_path=MOCK_PROMPT,
            output_xlsx=MOCK_OUTPUT
        )
        suggester.run() # This calls the class's run() method
    except Exception as e:
        print(f"Error during standalone test: {e}")
        import traceback
        traceback.print_exc()
