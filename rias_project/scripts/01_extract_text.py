import fitz  # PyMuPDF
import os
from pathlib import Path
from tqdm import tqdm
import argparse  # <-- NEW: for command-line options

# ------------------------------------------------------------------
# 1. CONFIGURATION (change only these lines for your project)
# ------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent.parent          # root of repo
INPUT_DIR  = SCRIPT_DIR / "data" / "raw_pdfs"                # <-- folder with PDFs
OUTPUT_DIR = SCRIPT_DIR / "data" / "extracted_text"          # <-- where .txt files go

# Create output folder if it does not exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 2. HELPER: extract plain text from a single PDF
# ------------------------------------------------------------------
def extract_text(pdf_path: Path) -> str:
    """
    Returns the full text of the PDF with a clear page-break marker.
    If a page contains no extractable text (e.g. scanned image), a note is added.
    """
    doc = fitz.open(str(pdf_path))               # fitz expects a string
    pages = []

    for page_num, page in enumerate(tqdm(doc, desc=f"Extracting pages from {pdf_path.stem}", unit="page"), start=1):
        text = page.get_text("text").strip()
        if not text:
            pages.append(f"[PAGE {page_num} - NO TEXT; maybe scanned image]")
        else:
            pages.append(text)

    doc.close()
    return "\n\n---PAGE BREAK---\n\n".join(pages)

# ------------------------------------------------------------------
# 3. COMMAND-LINE PARSER (NEW: to select specific PDFs or all)
# ------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Extract text from PDFs in raw_pdfs. Process one, multiple, or all."
)
parser.add_argument(
    "--pdfs",
    type=str,
    nargs="+",  # Accept one or more filenames
    help="Specific PDF filenames (e.g., 'file1.pdf file2.pdf'). Use 'all' to process everything.",
    default=None
)
args = parser.parse_args()

# ------------------------------------------------------------------
# 4. MAIN LOOP – process selected PDFs
# ------------------------------------------------------------------
if args.pdfs is None:
    print("❗ No --pdfs specified. Run with --help for usage.")
    print("Example: python script.py --pdfs file1.pdf file2.pdf")
    print("Or: python \"rias_project\scripts/01_extract_text.py\" --pdfs all")
    exit(0)

if "all" in args.pdfs:
    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))  # All PDFs
else:
    pdf_files = [INPUT_DIR / pdf_name for pdf_name in args.pdfs if (INPUT_DIR / pdf_name).exists()]
    if not pdf_files:
        print("❗ No valid PDFs found. Check filenames and try again.")
        exit(1)

for pdf_path in tqdm(pdf_files, desc="Extracting PDFs", unit="file"):
    txt_content = extract_text(pdf_path)

    # Save as <pdf_stem>.txt  (e.g. s11042-024-18872-y.pdf → s11042-024-18872-y.txt)
    txt_path = OUTPUT_DIR / (pdf_path.stem + ".txt")
    txt_path.write_text(txt_content + "\n", encoding="utf-8")   # trailing newline

print("\nDone! Extracted files →", OUTPUT_DIR)