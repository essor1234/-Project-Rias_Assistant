import os
import shutil
import random
import string
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time # Import the time module

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_ROOT = PROJECT_ROOT / "results"  # ALL SESSIONS HERE

MODULES = {
    "01": {"name": "Extract Text",   "file": "scripts/01_extract_text.py"},
    "06": {"name": "Extract Images", "file": "scripts/06_extract_images.py"},
    "03": {"name": "Compare Papers", "file": "scripts/03_generate_docs_excel.py"},
    "03b": {"name": "Merge Comparisons", "file": "scripts/03b_merge_comparisons.py"}, # Merge script
    "04": {"name": "Generate Edu",   "file": "scripts/04_generate_edu_materials.py"},
    "08": {"name": "Summarize",      "file": "scripts/08_summarize_papers_to_docx.py"},
    "07": {"name": "Suggest Next",   "file": "scripts/07_suggest_papers.py"},
}

# --- UPDATED STAGES ---
STAGE_1 = ["01", "06"] # Parallel
STAGE_2 = ["03"]       # Sequential (Individual compare runs per PDF)
STAGE_3 = ["04"]       # Sequential (Edu runs per PDF)
# --- MERGE (03b) IS NOW RUN SEPARATELY AT THE END ---
STAGE_4 = ["08", "07"] # Sequential (Summarize, Suggest)
ALL_STAGES = [STAGE_1, STAGE_2, STAGE_3, STAGE_4]
# Pipeline order for folder setup - 03b folder not needed per-pdf
PIPELINE_ORDER_SETUP = STAGE_1 + STAGE_2 + STAGE_3 + STAGE_4
# --- END UPDATED STAGES ---


# ----------------------------------------------------------------------
def import_run(step: str):
    # (import_run function remains the same as your latest version)
    if step not in MODULES:
        print(f"{step} | ERROR: Step '{step}' not defined in MODULES configuration.")
        return None
    mod_file = PROJECT_ROOT / MODULES[step]["file"]
    print(f"DEBUG: looking for module for step {step} -> {mod_file}")
    if not mod_file.exists():
        print(f"{step} | Missing module file: {mod_file}")
        scripts_dir = PROJECT_ROOT / "scripts"
        if scripts_dir.exists():
            print("Scripts folder listing:")
            for p in sorted(scripts_dir.glob("*.py")): print(f"  - {p.name}")
        else: print(f"Scripts folder not found at: {scripts_dir}")
        return None
    try:
        import importlib.util
        scripts_dir = PROJECT_ROOT / "scripts"
        scripts_path_str = str(scripts_dir.resolve())
        if scripts_path_str not in sys.path: sys.path.insert(0, scripts_path_str)
        spec = importlib.util.spec_from_file_location(f"module_{step}", mod_file)
        if spec is None:
             print(f"{step} | ERROR: Could not create module spec for {mod_file}.")
             return None
        mod = importlib.util.module_from_spec(spec)
        if mod is None:
             print(f"{step} | ERROR: Could not create module from spec for {mod_file}.")
             return None
        spec.loader.exec_module(mod)
        if hasattr(mod, "run") and callable(getattr(mod, "run")):
            return getattr(mod, "run")
        else:
             print(f"{step} | Module loaded but missing 'run' function in: {mod_file}")
             return None
    except ImportError as ie:
         import traceback
         print(f"{step} | Import error loading dependencies for {mod_file}: {ie}")
         traceback.print_exc(); return None
    except Exception as e:
        import traceback
        print(f"{step} | Unexpected error loading module {mod_file}: {e}")
        traceback.print_exc(); return None

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
            pdf_dir.mkdir(exist_ok=True)
            raw_dir = pdf_dir / "raw"
            raw_dir.mkdir(exist_ok=True)
            proc_dir = pdf_dir / "processed"
            if proc_dir.exists():
                print(f"Clearing existing processed data for {name}...")
                shutil.rmtree(proc_dir)
            proc_dir.mkdir(exist_ok=True)
            dest_pdf = raw_dir / pdf_path.name
            if not dest_pdf.exists() or os.path.getmtime(pdf_path) > os.path.getmtime(dest_pdf):
                 shutil.copy2(pdf_path, dest_pdf); print(f"Copied → {dest_pdf}")
            else: print(f"Using existing → {dest_pdf}")

            out_dirs = {}
            # Use PIPELINE_ORDER_SETUP for creating folders
            for step in PIPELINE_ORDER_SETUP:
                if step in MODULES and step != '03b': # Don't create 03b folder per PDF
                    folder_name = f"{step}_{MODULES[step]['name'].lower().replace(' ', '_')}_output"
                    folder = proc_dir / folder_name
                    folder.mkdir(exist_ok=True)
                    out_dirs[step] = folder

            pdf_info[name] = {
                "root": pdf_dir, "raw": raw_dir, "processed": proc_dir,
                "pdf_file": dest_pdf, "outputs": out_dirs, "results": {}
            }
        return pdf_info

    def run(self):
        pdf_info = self._setup_folders()
        all_pdf_results = {} # Store results per PDF name

        # --- Process each PDF through Stages 1-4 ---
        for pdf_name, info in pdf_info.items():
            print("\n" + "=" * 70)
            print(f"PROCESSING → {pdf_name}")
            print("=" * 70)

            pdf_file = info["pdf_file"]
            step_results_for_this_pdf = {"pdf": pdf_name}
            current_pdf_prev_results = {}

            for stage_idx, stage in enumerate(ALL_STAGES, 1): # ALL_STAGES now excludes 03b
                stage_name = f"STAGE {stage_idx}: [{', '.join(stage)}]"
                if stage_idx > 1:
                    print(f"\nWaiting 5 seconds before starting {stage_name}...")
                    time.sleep(5)
                print(f"\n{stage_name} → Running...")

                stage_results_this_pdf = {}
                run_in_parallel = stage_idx == 1 # Only Stage 1 runs in parallel

                if run_in_parallel:
                    with ThreadPoolExecutor(max_workers=len(stage)) as executor:
                        future_to_step = {}
                        for step in stage:
                            func = import_run(step)
                            out_dir = info["outputs"].get(step)
                            if out_dir is None:
                                 stage_results_this_pdf[step] = {"status": "error", "summary": f"output dir setup failed"}
                                 continue
                            if func is None:
                                stage_results_this_pdf[step] = {"status": "error", "summary": "module missing"}
                                continue
                            future = executor.submit(func, pdf_file, out_dir, current_pdf_prev_results)
                            future_to_step[future] = step

                        for future in as_completed(future_to_step):
                            step = future_to_step[future]
                            mod_name = MODULES.get(step, {}).get("name", f"Step {step}")
                            try:
                                result = future.result()
                                if not isinstance(result, dict): result = {"status": "success", "summary": f"Step {step} done"}
                                if "status" not in result: result["status"] = "success"
                                stage_results_this_pdf[step] = result
                                status = result["status"].upper(); summary = result.get("summary", ""); files = ", ".join(result.get("files", [])) or "—"
                                print(f"  {step} | {mod_name:<18} → {status}  {summary}  [{files}]")
                            except Exception as e:
                                import traceback; print(f"  {step} | {mod_name:<18} → ERROR"); traceback.print_exc()
                                stage_results_this_pdf[step] = {"status": "error", "error": str(e)}
                else:
                     # Run Stages 2, 3, 4 sequentially
                     print(f"Running {stage_name} steps sequentially.")
                     for step in stage:
                        mod_name = MODULES.get(step, {}).get("name", f"Step {step}")
                        func = import_run(step)
                        out_dir = info["outputs"].get(step)
                        if out_dir is None:
                             stage_results_this_pdf[step] = {"status": "error", "summary": f"output dir setup failed"}
                             continue
                        if func is None:
                            stage_results_this_pdf[step] = {"status": "error", "summary": "module missing"}
                            print(f"  {step} | {mod_name:<18} → ERROR  module missing"); continue
                        try:
                             result = func(pdf_file, out_dir, current_pdf_prev_results)
                             if not isinstance(result, dict): result = {"status": "success", "summary": f"Step {step} done"}
                             if "status" not in result: result["status"] = "success"
                             stage_results_this_pdf[step] = result
                             status = result["status"].upper(); summary = result.get("summary", ""); files = ", ".join(result.get("files", [])) or "—"
                             print(f"  {step} | {mod_name:<18} → {status}  {summary}  [{files}]")
                        except Exception as e:
                            import traceback; print(f"  {step} | {mod_name:<18} → ERROR"); traceback.print_exc()
                            stage_results_this_pdf[step] = {"status": "error", "error": str(e)}

                current_pdf_prev_results.update(stage_results_this_pdf)
                step_results_for_this_pdf.update(stage_results_this_pdf)

            all_pdf_results[pdf_name] = step_results_for_this_pdf # Store results for this PDF

        # --- Run Merge Step 03b ONCE after all PDFs are processed ---
        print("\n" + "=" * 70)
        print("Running Final Merge Step (03b)")
        print("=" * 70)
        merge_func = import_run("03b")
        if merge_func:
             try:
                 # Pass the session directory and None for unused args
                 merge_result = merge_func(None, self.session_dir, all_pdf_results)
                 print(f"  03b | Merge Comparisons → {merge_result.get('status', 'ERROR').upper()}  {merge_result.get('summary', '')}  [{', '.join(merge_result.get('files',[])) or '—'}]")
             except Exception as e:
                 import traceback
                 print(f"  03b | Merge Comparisons → ERROR")
                 traceback.print_exc()
        else:
            print("  03b | Merge Comparisons → SKIPPED (Module import failed)")


        # Convert results dict to list for final report
        final_report_list = list(all_pdf_results.values())
        self._final_report(final_report_list)
        return final_report_list # Return the list format expected by original code

    def _final_report(self, results_list: List[Dict]):
        # (_final_report remains largely the same, prints summary for each PDF)
        print("\n" + "=" * 70)
        print(f"PIPELINE FINISHED @ {datetime.now():%Y-%m-%d %H:%M:%S}")
        print(f"SESSION ID: {self.session_id}")
        print(f"ALL RESULTS IN: results/{self.session_id}")
        merged_file = self.session_dir / "03_comparison_merged.xlsx" # Check final merge file location
        if merged_file.exists():
             print(f"MERGED COMPARISON: results/{self.session_id}/{merged_file.name}")
        else:
             print("MERGED COMPARISON: Not found (Check logs for step 03b).")
        print("=" * 70)

        for res in results_list:
            pdf = res["pdf"]
            print(f"\n{pdf}")
            steps_shown_for_pdf = set()
            # Iterate through defined stages, excluding 03b here
            for stage_idx, stage in enumerate(ALL_STAGES, 1): # ALL_STAGES excludes 03b now
                print(f"  STAGE {stage_idx}: [{', '.join(stage)}]")
                for step in stage:
                    if step in steps_shown_for_pdf: continue # Should not happen with current structure
                    data = res.get(step)
                    if data is None:
                        print(f"    {step} {MODULES.get(step, {}).get('name', step):<18} → ❓ UNKNOWN")
                        continue
                    name = MODULES.get(step, {}).get("name", f"Step {step}")
                    st = data.get("status", "unknown").upper()
                    summ = data.get("summary", "")
                    files = ", ".join(data.get("files", [])) or "—"
                    icon = "✅ SUCCESS" if st == "SUCCESS" else "❌ ERROR" if st == "ERROR" else "⏭️ SKIPPED"
                    print(f"    {step} {name:<18} → {icon}  {summ}  [{files}]")
                    steps_shown_for_pdf.add(step)

        print(f"\nAll per-PDF outputs saved in:\n  results/{self.session_id}/<pdf_name>/processed/")
        if merged_file.exists():
             print(f"Session-wide merged comparison saved in:\n  results/{self.session_id}/")
        print("=" * 70)

# ----------------------------------------------------------------------
def get_pdfs_from_folder(folder_path: Path, limit: Optional[int] = None) -> List[Path]:
    # (remains the same)
    if not folder_path.exists(): return []
    pdfs = sorted(folder_path.glob("*.pdf"))
    if not pdfs: print(f"No PDFs in {folder_path}"); return []
    if limit: limit = min(limit, len(pdfs)); pdfs = pdfs[:limit]
    print(f"Found {len(pdfs)} PDF(s) in {folder_path}")
    for p in pdfs: print(f"  • {p.name}")
    return pdfs

# ----------------------------------------------------------------------
def main():
    # (main function remains the same, including pdfs initialization)
    print("\nPDF → AI Research Pipeline")
    # Updated description to reflect new stage structure and final merge step
    print("Stages: [01+06](Par) → [03](Seq) → [04](Seq) → [08+07](Seq) → [03b Merge](Final)")
    print("ALL RESULTS SAVED IN: ./results/<random_session>/\n")

    if len(sys.argv) < 2:
        print("Usage:\n  python main.py <folder_path> [limit]\n  python main.py <file.pdf>")
        sys.exit(1)
    input_path = Path(sys.argv[1]); limit = None
    if not input_path.exists(): print(f"Error: Path not found: {input_path}"); sys.exit(1)

    pdfs: List[Path] = []
    if input_path.is_file():
        if input_path.suffix.lower() == ".pdf": pdfs = [input_path]; print(f"Found 1 PDF file: {input_path.name}")
        else: print(f"Error: Input file is not a .pdf: {input_path.name}"); sys.exit(1)
        if len(sys.argv) > 2: print("Note: Limit ignored for single file.")
    elif input_path.is_dir():
        if len(sys.argv) > 2:
            try: limit = int(sys.argv[2]); assert limit > 0
            except: print("Invalid limit. Must be positive number."); sys.exit(1)
        pdfs = get_pdfs_from_folder(input_path, limit)
        if not pdfs: print(f"No PDF files found in folder: {input_path}"); sys.exit(1)
        if limit and len(pdfs) < limit: print(f"Only {len(pdfs)} PDFs found (limit was {limit}).")
    else: print(f"Error: Not a valid file or folder: {input_path}"); sys.exit(1)
    if not pdfs: print("No PDF files selected."); sys.exit(1)

    confirm = input(f"\nProcess {len(pdfs)} PDF(s)? (y/n): ").strip().lower()
    if confirm != 'y': print("Aborted."); return

    pipeline = PDFPipeline(pdfs)
    pipeline.run()

if __name__ == "__main__":
    main()

