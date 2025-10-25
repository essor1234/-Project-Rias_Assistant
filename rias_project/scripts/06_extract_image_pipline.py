import os
from pathlib import Path
from typing import Union, Iterable, Optional
from extract_image.extract_images import extract_images_from_pdf
from extract_image.render_pages import render_pdf_pages


def process_pdfs_in_directory(
    input_dir: Union[str, Path],
    output_dir: Union[str, Path],
    *,
    pdf_names: Optional[Union[str, Iterable[str]]] = None,
    pattern: Optional[str] = None,
    zoom: int = 4
) -> None:
    """
    Process selected PDFs from *input_dir*.

    - For every processed PDF a sub-folder named **exactly like the PDF** (without .pdf)
      is created inside *output_dir*.
    - Both extracted images **and** rendered pages are saved into that sub-folder.

    Args:
        input_dir: Folder that contains the source PDFs.
        output_dir: Base folder where per-PDF sub-folders will be created.
        pdf_names: Single filename **or** iterable of filenames (without path)
                   to process.  If omitted, all PDFs are processed (subject to *pattern*).
        pattern: Optional glob pattern (e.g. "*invoice*.pdf") applied **after** pdf_names.
        zoom: Zoom factor for page rendering (default = 4).

    Examples
    --------
    >>> process_pdfs_in_directory("raw", "out")
    # -> all PDFs

    >>> process_pdfs_in_directory("raw", "out", pdf_names="report.pdf")
    # -> only report.pdf

    >>> process_pdfs_in_directory("raw", "out", pdf_names=["a.pdf","b.pdf"])
    # -> a.pdf and b.pdf

    >>> process_pdfs_in_directory("raw", "out", pattern="*2025*.pdf")
    # -> every PDF that contains "2025" in its name
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # ------------------------------------------------------------------ validation
    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_path}")
    if not input_path.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ collect PDFs
    all_pdfs = {p.name: p for p in input_path.glob("*.pdf")}

    if not all_pdfs:
        print(f"No PDF files found in {input_path}")
        return

    # 1. filter by explicit names
    if pdf_names is not None:
        if isinstance(pdf_names, str):
            pdf_names = [pdf_names]
        selected = {name for name in pdf_names if name in all_pdfs}
        missing = set(pdf_names) - selected
        if missing:
            print(f"Warning: These requested files were not found: {', '.join(missing)}")
        pdf_paths = [all_pdfs[name] for name in selected]
    else:
        pdf_paths = list(all_pdfs.values())

    # 2. optional glob pattern on the remaining list
    if pattern:
        pdf_paths = [p for p in pdf_paths if p.match(pattern)]

    if not pdf_paths:
        print("No PDFs matched the selection criteria.")
        return

    print(f"Found {len(pdf_paths)} PDF(s) to process...\n")

    # ------------------------------------------------------------------ process each PDF
    for pdf_path in sorted(pdf_paths):
        pdf_stem = pdf_path.stem                      # e.g. "Invoice_001"
        pdf_out_dir = output_path / pdf_stem
        pdf_out_dir.mkdir(exist_ok=True)

        print(f"Processing {pdf_path.name} → {pdf_out_dir.name}/")

        # ---- extract images -------------------------------------------------
        extract_images_from_pdf(str(pdf_path), str(pdf_out_dir))

        # ---- render pages ---------------------------------------------------
        # render_pdf_pages(str(pdf_path), str(pdf_out_dir), zoom=zoom)

    print(f"\nAll {len(pdf_paths)} PDF(s) processed successfully!")
    print(f"   Output saved in: {output_path}")


# ---------------------------------------------------------------------- demo
if __name__ == "__main__":
    SCRIPT_DIR = Path(__file__).parent.parent

    # 1. Process **everything**
    # process_pdfs_in_directory(
    #     input_dir=SCRIPT_DIR / "data/raw_pdfs",
    #     output_dir=SCRIPT_DIR / "data/processed_outputs"
    # )

    # 2. Process **only two specific files**
    # process_pdfs_in_directory(
    #     input_dir=SCRIPT_DIR / "data/raw_pdfs",
    #     output_dir=SCRIPT_DIR / "data/processed_outputs",
    #     pdf_names=["report_q4.pdf", "invoice_2025.pdf"]
    # )

    # 3. Process **all PDFs that contain "2025"**
    process_pdfs_in_directory(
        input_dir=SCRIPT_DIR / "data/raw_pdfs",
        output_dir=SCRIPT_DIR / "data/extracted_image",
        pattern="rias_project\data/raw_pdfs/test4.pdf"
    )