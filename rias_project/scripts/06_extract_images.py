import os
from pathlib import Path
from typing import Union, Iterable, Optional
from extract_image.extract_images import extract_images_from_pdf
from extract_image.render_pages import render_pdf_pages


class PDFImageExtractor:
    """
    Extracts images and renders pages from PDFs into structured folders.

    Example:
        extractor = PDFImageExtractor("data/raw_pdfs", "data/extracted_images")
        extractor.run(pattern="*report*.pdf", zoom=4)
    """

    def __init__(self, input_dir: Union[str, Path], output_dir: Union[str, Path]):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        if not self.input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {self.input_dir}")
        if not self.input_dir.is_dir():
            raise NotADirectoryError(f"Input path is not a directory: {self.input_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Core method: process a single PDF
    # ------------------------------------------------------------------
    def process_single_pdf(self, pdf_path: Path, zoom: int = 4) -> None:
        """Extract images and render pages from a single PDF."""
        
        # ▼▼▼ THIS IS THE FIX ▼▼▼
        # The 'main.py' script already provides the final, correct output dir.
        # We should save images directly into it, not in a new subfolder.
        pdf_out_dir = self.output_dir
        # ▲▲▲ END OF FIX ▲▲▲

        print(f"Processing {pdf_path.name} → {pdf_out_dir.name}/")

        # Extract embedded images
        extract_images_from_pdf(str(pdf_path), str(pdf_out_dir))

        # Optionally render full pages (disabled if not needed)
        # render_pdf_pages(str(pdf_path), str(pdf_out_dir), zoom=zoom)

    # ------------------------------------------------------------------
    # Process multiple PDFs
    # ------------------------------------------------------------------
    def process_pdfs(
        self,
        *,
        pdf_names: Optional[Union[str, Iterable[str]]] = None,
        pattern: Optional[str] = None,
        zoom: int = 4
    ) -> None:
        """
        Process selected PDFs and extract images + render pages.

        Args:
            pdf_names: Specific PDF filenames (string or list).
            pattern: Optional glob pattern (e.g. "*2025*.pdf").
            zoom: Page rendering zoom factor (default=4).
        """
        all_pdfs = {p.name: p for p in self.input_dir.glob("*.pdf")}
        if not all_pdfs:
            print(f"No PDF files found in {self.input_dir}")
            return

        # 1️⃣ Filter by names
        if pdf_names is not None:
            if isinstance(pdf_names, str):
                pdf_names = [pdf_names]
            selected = {name for name in pdf_names if name in all_pdfs}
            missing = set(pdf_names) - selected
            if missing:
                print(f"⚠️ Warning: Not found: {', '.join(missing)}")
            pdf_paths = [all_pdfs[name] for name in selected]
        else:
            pdf_paths = list(all_pdfs.values())

        # 2️⃣ Filter by glob pattern
        if pattern:
            pdf_paths = [p for p in pdf_paths if p.match(pattern)]

        if not pdf_paths:
            print("No PDFs matched the selection criteria.")
            return

        print(f"📘 Found {len(pdf_paths)} PDF(s) to process...\n")

        for pdf_path in sorted(pdf_paths):
            self.process_single_pdf(pdf_path, zoom=zoom)

        print(f"\n✅ All {len(pdf_paths)} PDF(s) processed successfully!")
        print(f"   Output saved in: {self.output_dir}")

    # ------------------------------------------------------------------
    # Helper: run entire pipeline
    # ------------------------------------------------------------------
    # This function should REPLACE the old `def run(...)` 
# at the end of your 'scripts/01_extract_text.py' file.

def run(pdf_path, out_dir, prev=None):
    """Bridge function for main.py pipeline."""
    try:
        p = Path(pdf_path)
        out = Path(out_dir)
        
        # Create extractor with correct paths
        extractor = PDFImageExtractor(
            input_dir=p.parent,  
            output_dir=out
        )
        
        # Process just this single PDF
        extractor.process_single_pdf(p, zoom=4)
        
        # Return success with list of generated files
        # This will now correctly find the images inside 'out_dir'
        files = [f.name for f in out.glob("*") if f.is_file()]
        return {
            "status": "success", 
            "files": files,
            "summary": "images extracted"
        }
        
    except Exception as e:
        print(f"ERROR in extract_images: {e}")
        return {"status": "error", "error": str(e)}

# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# Optional CLI entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Extract images and render pages from PDFs.")
    parser.add_argument("input_dir", type=str, help="Path to folder containing PDFs")
    parser.add_argument("output_dir", type=str, help="Path to output folder")
    parser.add_argument("--pdfs", type=str, nargs="+", help="Specific PDF filenames")
    parser.add.argument("--pattern", type=str, help="Glob pattern (e.g. '*invoice*.pdf')")
    parser.add.argument("--zoom", type=int, default=4, help="Zoom factor for rendering")
    args = parser.parse.args()

    extractor = PDFImageExtractor(args.input_dir, args.output_dir)
    pdf_names = None if not args.pdfs or args.pdfs == ["all"] else args.pdfs
    
    # This is the old .run() method, it's fine for CLI use
    extractor.process_pdfs(pdf_names=pdf_names, pattern=args.pattern, zoom=args.zoom)
# ---------------------------------------------------------------------- #
# import os
# from pathlib import Path
# from typing import Union, Iterable, Optional
# from extract_image.extract_images import extract_images_from_pdf
# from extract_image.render_pages import render_pdf_pages


# def process_pdfs_in_directory(
#     input_dir: Union[str, Path],
#     output_dir: Union[str, Path],
#     *,
#     pdf_names: Optional[Union[str, Iterable[str]]] = None,
#     pattern: Optional[str] = None,
#     zoom: int = 4
# ) -> None:
#     """
#     Process selected PDFs from *input_dir*.

#     - For every processed PDF a sub-folder named **exactly like the PDF** (without .pdf)
#       is created inside *output_dir*.
#     - Both extracted images **and** rendered pages are saved into that sub-folder.

#     Args:
#         input_dir: Folder that contains the source PDFs.
#         output_dir: Base folder where per-PDF sub-folders will be created.
#         pdf_names: Single filename **or** iterable of filenames (without path)
#                    to process.  If omitted, all PDFs are processed (subject to *pattern*).
#         pattern: Optional glob pattern (e.g. "*invoice*.pdf") applied **after** pdf_names.
#         zoom: Zoom factor for page rendering (default = 4).

#     Examples
#     --------
#     >>> process_pdfs_in_directory("raw", "out")
#     # -> all PDFs

#     >>> process_pdfs_in_directory("raw", "out", pdf_names="report.pdf")
#     # -> only report.pdf

#     >>> process_pdfs_in_directory("raw", "out", pdf_names=["a.pdf","b.pdf"])
#     # -> a.pdf and b.pdf

#     >>> process_pdfs_in_directory("raw", "out", pattern="*2025*.pdf")
#     # -> every PDF that contains "2025" in its name
#     """
#     input_path = Path(input_dir)
#     output_path = Path(output_dir)

#     # ------------------------------------------------------------------ validation
#     if not input_path.exists():
#         raise FileNotFoundError(f"Input directory not found: {input_path}")
#     if not input_path.is_dir():
#         raise NotADirectoryError(f"Input path is not a directory: {input_path}")

#     output_path.mkdir(parents=True, exist_ok=True)

#     # ------------------------------------------------------------------ collect PDFs
#     all_pdfs = {p.name: p for p in input_path.glob("*.pdf")}

#     if not all_pdfs:
#         print(f"No PDF files found in {input_path}")
#         return

#     # 1. filter by explicit names
#     if pdf_names is not None:
#         if isinstance(pdf_names, str):
#             pdf_names = [pdf_names]
#         selected = {name for name in pdf_names if name in all_pdfs}
#         missing = set(pdf_names) - selected
#         if missing:
#             print(f"Warning: These requested files were not found: {', '.join(missing)}")
#         pdf_paths = [all_pdfs[name] for name in selected]
#     else:
#         pdf_paths = list(all_pdfs.values())

#     # 2. optional glob pattern on the remaining list
#     if pattern:
#         pdf_paths = [p for p in pdf_paths if p.match(pattern)]

#     if not pdf_paths:
#         print("No PDFs matched the selection criteria.")
#         return

#     print(f"Found {len(pdf_paths)} PDF(s) to process...\n")

#     # ------------------------------------------------------------------ process each PDF
#     for pdf_path in sorted(pdf_paths):
#         pdf_stem = pdf_path.stem                      # e.g. "Invoice_001"
#         pdf_out_dir = output_path / pdf_stem
#         pdf_out_dir.mkdir(exist_ok=True)

#         print(f"Processing {pdf_path.name} → {pdf_out_dir.name}/")

#         # ---- extract images -------------------------------------------------
#         extract_images_from_pdf(str(pdf_path), str(pdf_out_dir))

#         # ---- render pages ---------------------------------------------------
#         # render_pdf_pages(str(pdf_path), str(pdf_out_dir), zoom=zoom)

#     print(f"\nAll {len(pdf_paths)} PDF(s) processed successfully!")
#     print(f"   Output saved in: {output_path}")


# # ---------------------------------------------------------------------- demo
# if __name__ == "__main__":
#     SCRIPT_DIR = Path(__file__).parent.parent

#     # 1. Process **everything**
#     # process_pdfs_in_directory(
#     #     input_dir=SCRIPT_DIR / "data/raw_pdfs",
#     #     output_dir=SCRIPT_DIR / "data/processed_outputs"
#     # )

#     # 2. Process **only two specific files**
#     # process_pdfs_in_directory(
#     #     input_dir=SCRIPT_DIR / "data/raw_pdfs",
#     #     output_dir=SCRIPT_DIR / "data/processed_outputs",
#     #     pdf_names=["report_q4.pdf", "invoice_2025.pdf"]
#     # )

#     # 3. Process **all PDFs that contain "2025"**
#     process_pdfs_in_directory(
#         input_dir=SCRIPT_DIR / "data/raw_pdfs",
#         output_dir=SCRIPT_DIR / "data/extracted_image",
#         pattern="rias_project\data/raw_pdfs/test4.pdf"
#     )