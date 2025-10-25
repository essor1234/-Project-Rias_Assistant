import fitz  # PyMuPDF
import argparse
from pathlib import Path
from typing import Union, Iterable, Optional
from tqdm import tqdm


def extract_text_from_pdf(pdf_path: Path, output_dir: Path) -> None:
    """
    Extract text from a single PDF and save it as .txt inside a dedicated folder.
    """
    doc = fitz.open(str(pdf_path))
    pages = []

    for page_num, page in enumerate(
        tqdm(doc, desc=f"  Pages in {pdf_path.stem}", unit="page", leave=False), start=1
    ):
        text = page.get_text("text").strip()
        if not text:
            pages.append(f"[PAGE {page_num} - NO TEXT; maybe scanned image]")
        else:
            pages.append(text)

    doc.close()
    full_text = "\n\n---PAGE BREAK---\n\n".join(pages)

    # Save to: output_dir/<pdf_stem>/<pdf_stem>.txt
    txt_path = output_dir / f"{pdf_path.stem}.txt"
    txt_path.write_text(full_text + "\n", encoding="utf-8")


def process_pdfs_for_text(
    input_dir: Union[str, Path],
    output_dir: Union[str, Path],
    *,
    pdf_names: Optional[Union[str, Iterable[str]]] = None,
    pattern: Optional[str] = None
) -> None:
    """
    Extract text from selected PDFs and save each into its own named subfolder.

    Args:
        input_dir: Directory containing source PDFs.
        output_dir: Base directory where per-PDF folders will be created.
        pdf_names: Optional list of specific PDF filenames (without path).
                   Use a string for one, or list for many.
        pattern: Optional glob pattern (e.g., "*2025*.pdf") to filter PDFs.

    Output Structure:
        output_dir/
        └── MyReport/
            └── MyReport.txt
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # -------------------------- Validation --------------------------
    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_path}")
    if not input_path.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    # -------------------------- Collect PDFs --------------------------
    all_pdfs = {p.name: p for p in input_path.glob("*.pdf")}
    if not all_pdfs:
        print(f"No PDF files found in {input_path}")
        return

    # Filter by explicit names
    if pdf_names is not None:
        if isinstance(pdf_names, str):
            pdf_names = [pdf_names]
        selected = {name for name in pdf_names if name in all_pdfs}
        missing = set(pdf_names) - selected
        if missing:
            print(f"Warning: Not found: {', '.join(missing)}")
        pdf_paths = [all_pdfs[name] for name in selected]
    else:
        pdf_paths = list(all_pdfs.values())

    # Apply glob pattern if given
    if pattern:
        pdf_paths = [p for p in pdf_paths if p.match(pattern)]

    if not pdf_paths:
        print("No PDFs matched the selection criteria.")
        return

    print(f"Found {len(pdf_paths)} PDF(s) to extract text from...\n")

    # -------------------------- Process Each PDF --------------------------
    for pdf_path in tqdm(sorted(pdf_paths), desc="Extracting Text", unit="file"):
        pdf_stem = pdf_path.stem
        pdf_out_dir = output_path / pdf_stem
        pdf_out_dir.mkdir(exist_ok=True)

        print(f"  → {pdf_path.name} → {pdf_out_dir.name}/")

        extract_text_from_pdf(pdf_path, pdf_out_dir)

    print(f"\nAll {len(pdf_paths)} PDF(s) processed!")
    print(f"   Text saved in: {output_path}")


# ----------------------------------------------------------------------
# CLI Entry Point (optional – same behavior as before)
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Extract text from PDFs. Save each into its own folder."
    )
    parser.add_argument(
        "input_dir",
        type=str,
        help="Path to folder containing input PDFs"
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="Path to base output folder (per-PDF subfolders will be created)"
    )
    parser.add_argument(
        "--pdfs",
        type=str,
        nargs="+",
        help="Specific PDF filenames (e.g. 'file1.pdf file2.pdf'). Use 'all' to process all.",
        default=None
    )
    parser.add_argument(
        "--pattern",
        type=str,
        help="Glob pattern to filter PDFs (e.g. '*invoice*.pdf')",
        default=None
    )

    args = parser.parse_args()

    pdf_names = None
    if args.pdfs and args.pdfs != ["all"]:
        pdf_names = args.pdfs

    process_pdfs_for_text(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        pdf_names=pdf_names,
        pattern=args.pattern
    )

# ...existing code...

if __name__ == "__main__":
    SCRIPT_DIR = Path(__file__).resolve().parent.parent
    process_pdfs_for_text(
        input_dir=SCRIPT_DIR / "data/raw_pdfs",
        output_dir=SCRIPT_DIR / "data/extracted_text",
        pattern="rias_project\data/raw_pdfs\The_MUSCIMA_Dataset_for_Handwritten_Optical_Music_Recognition.pdf"  # Just use the filename instead of full path
    )