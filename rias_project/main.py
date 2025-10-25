import os
import shutil
import random
import string
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_ROOT = PROJECT_ROOT / "results"  # ALL SESSIONS HERE

MODULES = {
    "01": {"name": "Extract Text",   "file": "scripts/01_extract_text.py"},
    # fixed filename (was pointing to non-existent *_pipline)
    "06": {"name": "Extract Images", "file": "scripts/06_extract_images.py"},
    "03": {"name": "Compare Papers", "file": "scripts/03_generate_docs_excel.py"},
    "04": {"name": "Generate Edu",   "file": "scripts/04_generate_edu_materials.py"},
    "08": {"name": "Summarize",      "file": "scripts/08_summarize_papers_to_docx.py"},
    "07": {"name": "Suggest Next",   "file": "scripts/07_suggest_papers.py"},
}

STAGE_1 = ["01", "06"]
STAGE_2 = ["03", "04"]
STAGE_3 = ["08", "07"]
ALL_STAGES = [STAGE_1, STAGE_2, STAGE_3]
PIPELINE_ORDER = STAGE_1 + STAGE_2 + STAGE_3

# ----------------------------------------------------------------------
def import_run(step: str):
    mod_file = PROJECT_ROOT / MODULES[step]["file"]
    # Diagnostic output
    print(f"DEBUG: looking for module for step {step} -> {mod_file}")
    if not mod_file.exists():
        print(f"{step} | Missing module file: {mod_file}")
        # show scripts folder contents for quick inspection
        scripts_dir = PROJECT_ROOT / "scripts"
        if scripts_dir.exists():
            print("Scripts folder listing:")
            for p in sorted(scripts_dir.glob("*")):
                print(f"  - {p.name}")
        else:
            print(f"Scripts folder not found at: {scripts_dir}")
        return None
    try:
        import importlib.util

        # Ensure scripts/ is on sys.path so imports inside scripts (e.g. "import extract_image...") work
        scripts_dir = PROJECT_ROOT / "scripts"
        scripts_path_str = str(scripts_dir.resolve())
        if scripts_path_str not in sys.path:
            sys.path.insert(0, scripts_path_str)

        spec = importlib.util.spec_from_file_location(f"module_{step}", mod_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Accept several common entry-point names; wrap into a callable accepting (pdf_path, out_dir, prev)
        candidates = [
            "run", "main", "process", "process_paper", "process_pdfs_in_directory",
            "extract_text_from_pdf", "extract_images_from_pdf", "process_pdfs_for_text",
            "compare_papers_to_excel", "create_ppt", "generate_edu_materials", "summarize_paper"
        ]
        for name in candidates:
            if hasattr(mod, name) and callable(getattr(mod, name)):
                func = getattr(mod, name)
                def runner(pdf_path, out_dir, prev, func=func):
                    # Try calling with (pdf_path, out_dir, prev), fallback to fewer args.
                    try:
                        return func(pdf_path, out_dir, prev)
                    except TypeError:
                        try:
                            return func(pdf_path, out_dir)
                        except TypeError:
                            return func(pdf_path)
                return runner

        # Try to pick up any callable matching common prefixes if no explicit name present
        for attr in dir(mod):
            if attr.startswith(("process_", "generate_", "extract_", "summarize_", "compare_")):
                f = getattr(mod, attr)
                if callable(f):
                    def runner2(pdf_path, out_dir, prev, f=f):
                        try:
                            return f(pdf_path, out_dir, prev)
                        except TypeError:
                            try:
                                return f(pdf_path, out_dir)
                            except TypeError:
                                return f(pdf_path)
                    print(f"{step} | Using entry {attr} from {mod_file.name}")
                    return runner2

        # nothing found
        print(f"{step} | Module loaded but missing run()/main()/process() in: {mod_file}")
        return None
    except Exception as e:
        print(f"{step} | Import error loading {mod_file}: {e}")
        return None

# ----------------------------------------------------------------------
class PDFPipeline:
    def __init__(self, pdf_paths: List[Path]):
        self.pdf_paths = [p.resolve() for p in pdf_paths]
        self.session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        self.session_dir = PROCESSED_ROOT / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nSession folder: {self.session_dir}\n")

    def _setup_folders(self) -> Dict[str, Dict]:
        pdf_info = {}
        for pdf_path in self.pdf_paths:
            name = pdf_path.stem
            pdf_dir = self.session_dir / name
            # Clear any existing processed directory to prevent interference
            proc_dir = pdf_dir / "processed"
            if proc_dir.exists():
                shutil.rmtree(proc_dir)
            
            # Create fresh directories
            pdf_dir.mkdir(exist_ok=True)
            raw_dir = pdf_dir / "raw"
            raw_dir.mkdir(exist_ok=True)
            proc_dir.mkdir(exist_ok=True)

            # Copy PDF to raw directory
            dest_pdf = raw_dir / pdf_path.name
            shutil.copy2(pdf_path, dest_pdf)
            print(f"Copied → {dest_pdf}")

            # Create output directories with consistent naming
            out_dirs = {}
            for step in PIPELINE_ORDER:
                folder_name = f"{step}_{MODULES[step]['name'].lower().replace(' ', '_')}_output"
                folder = proc_dir / folder_name
                folder.mkdir(exist_ok=True)
                out_dirs[step] = folder

            pdf_info[name] = {
                "root": pdf_dir,
                "raw": raw_dir,
                "processed": proc_dir,
                "pdf_file": dest_pdf,
                "outputs": out_dirs,
                "results": {}  # Store results for each step
            }
        return pdf_info

    def run(self):
        pdf_info = self._setup_folders()
        all_results = []

        for pdf_name, info in pdf_info.items():
            print("\n" + "=" * 70)
            print(f"PROCESSING → {pdf_name}")
            print("=" * 70)

            pdf_file = info["pdf_file"]
            step_results = {"pdf": pdf_name}
            prev_results = {}  # Store results per stage

            for stage_idx, stage in enumerate(ALL_STAGES, 1):
                stage_name = f"STAGE {stage_idx}: [{', '.join(stage)}]"
                print(f"\n{stage_name} → Running in parallel...")

                stage_results = {}
                with ThreadPoolExecutor(max_workers=len(stage)) as executor:
                    future_to_step = {}
                    for step in stage:
                        func = import_run(step)
                        out_dir = info["outputs"][step]
                        if func is None:
                            stage_results[step] = {"status": "error", "summary": "module missing"}
                            continue
                        
                        # Pass all previous results, not just the last one
                        future = executor.submit(func, pdf_file, out_dir, prev_results)
                        future_to_step[future] = step

                    for future in as_completed(future_to_step):
                        step = future_to_step[future]
                        mod_name = MODULES[step]["name"]
                        try:
                            result = future.result()
                            if not isinstance(result, dict):
                                result = {"status": "success", "summary": "done"}
                            if "status" not in result:
                                result["status"] = "success"

                            # Store result for future stages
                            prev_results[step] = result
                            stage_results[step] = result

                            status = result["status"].upper()
                            summary = result.get("summary", "")
                            files = ", ".join(result.get("files", [])) or "—"
                            print(f"  {step} | {mod_name:<18} → {status}  {summary}  [{files}]")

                        except Exception as e:
                            err = f"EXCEPTION: {e}"
                            print(f"  {step} | {mod_name:<18} → ERROR  {err}")
                            stage_results[step] = {"status": "error", "error": str(e)}

                # Update step results with all stage results
                step_results.update(stage_results)
                info["results"].update(stage_results)

            all_results.append(step_results)

        self._final_report(all_results)
        return all_results

    def _final_report(self, results: List[Dict]):
        print("\n" + "=" * 70)
        print(f"PIPELINE FINISHED @ {datetime.now():%Y-%m-%d %H:%M:%S}")
        print(f"SESSION ID: {self.session_id}")
        print(f"ALL RESULTS IN: results/{self.session_id}")
        print("=" * 70)

        for res in results:
            pdf = res["pdf"]
            print(f"\n{pdf}")
            for stage_idx, stage in enumerate(ALL_STAGES, 1):
                print(f"  STAGE {stage_idx}: [{', '.join(stage)}]")
                for step in stage:
                    data = res.get(step, {})
                    name = MODULES[step]["name"]
                    st = data.get("status", "unknown").upper()
                    summ = data.get("summary", "")
                    files = ", ".join(data.get("files", [])) or "—"
                    icon = "SUCCESS" if st == "SUCCESS" else "ERROR" if st == "ERROR" else "SKIPPED"
                    print(f"    {step} {name:<18} → {icon}  {summ}  [{files}]")

        print(f"\nAll outputs saved in:\n  results/{self.session_id}\n")
        print("=" * 70)


# ----------------------------------------------------------------------
def get_pdfs_from_folder(folder_path: Path, limit: Optional[int] = None) -> List[Path]:
    if not folder_path.exists():
        print(f"Folder not found: {folder_path}")
        return []
    pdfs = sorted(folder_path.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {folder_path}")
        return []
    if limit:
        pdfs = pdfs[:limit]
    print(f"Found {len(pdfs)} PDF(s) in {folder_path}")
    for p in pdfs:
        print(f"  • {p.name}")
    return pdfs


# ----------------------------------------------------------------------
# ▼▼▼ THIS IS THE ONLY FUNCTION THAT HAS CHANGED ▼▼▼
# ----------------------------------------------------------------------
def main():
    print("\nPDF → AI Research Pipeline")
    print("Stages: [01+06] → [03+04] → [08+07] (each pair in parallel)")
    print("ALL RESULTS SAVED IN: ./results/<random_session>/\n")

    # === COMMAND LINE ARGUMENT ===
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py <path_to_folder>      # Process all PDFs in a folder")
        print("  python main.py <path_to_folder> 5    # Process first 5 PDFs in a folder")
        print("  python main.py <path_to_file.pdf>  # Process a single PDF file")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    limit = None
    
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}")
        sys.exit(1)

    # === GET PDFs ===
    pdfs: List[Path] = []
    
    if input_path.is_file():
        # --- Handle single file input ---
        if input_path.suffix.lower() == ".pdf":
            print(f"Found 1 PDF file: {input_path.name}")
            pdfs = [input_path]
            if len(sys.argv) > 2:
                print("Note: Limit argument is ignored when processing a single file.")
        else:
            print(f"Error: Input file is not a .pdf: {input_path.name}")
            sys.exit(1)
    
    elif input_path.is_dir():
        # --- Handle folder input ---
        if len(sys.argv) > 2:
            try:
                limit = int(sys.argv[2])
                if limit <= 0:
                    print("Limit must be a positive number.")
                    sys.exit(1)
            except ValueError:
                print("Invalid limit. Must be a positive number.")
                sys.exit(1)
        
        pdfs = get_pdfs_from_folder(input_path, limit)
        
        if limit and len(pdfs) < limit:
             print(f"Only {len(pdfs)} PDFs found (limit was {limit}). Proceeding with all found.")
    
    else:
        print(f"Error: Input path is not a valid file or folder: {input_path}")
        sys.exit(1)

    if not pdfs:
        print("No PDF files to process.")
        sys.exit(1)

    # === CONFIRM AND RUN ===
    confirm = input(f"\nProcess {len(pdfs)} PDF(s)? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        return

    pipeline = PDFPipeline(pdfs)
    pipeline.run()


if __name__ == "__main__":
    main()