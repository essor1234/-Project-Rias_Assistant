import json
import os
import time
import base64
from datetime import datetime
from pathlib import Path
from typing import Union, Iterable, Optional
from tqdm import tqdm
import openpyxl  # For Excel handling

from openai import OpenAI
from dotenv import load_dotenv


# ------------------------------------------------------------------
# Load .env (API key, etc.)
# ------------------------------------------------------------------
load_dotenv()  # Looks for .env in cwd or parent dirs


def encode_image(image_path: Path) -> str:
    """Encode image to base64 string for OpenAI API."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_paper_info(
    txt_path: Path,
    headers: list[str],
    prompt_template: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 1200,
    temperature: float = 0.0
) -> dict:
    """
    Use LLM to extract structured info from a paper's .txt (and images if present).
    Returns JSON dict matching the template headers.
    """
    # Use the same folder as .txt for images
    images_dir = txt_path.parent
    image_files = (
        sorted(images_dir.glob("*.png")) +
        sorted(images_dir.glob("*.jpg")) +
        sorted(images_dir.glob("*.jpeg"))
    )
    if not image_files:
        print(f"Warning: No images for {txt_path.stem}")

    # Load text
    full_text = txt_path.read_text(encoding="utf-8")
    text_content = full_text[:30000]
    if len(full_text) > 30000:
        text_content += "\n\n[Text truncated for length]"

    # Prepare messages
    system_prompt = (
        "You are a precise research paper analyst. Extract key information "
        f"as JSON with exactly these keys: {', '.join(headers)}. "
        "Use the text and any images (with positional context) to fill values accurately."
    )
    messages = [{"role": "system", "content": system_prompt}]

    # Add images with context
    image_contexts = []
    for idx, img_path in enumerate(image_files, 1):
        b64 = encode_image(img_path)
        section = "top" if idx <= len(image_files)//3 else "middle" if idx <= 2*len(image_files)//3 else "bottom"
        caption = f"Image {idx} ({img_path.name}) - in {section} section."

        image_contexts.extend([
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": caption}
        ])

    user_content = [
        {"type": "text", "text": prompt_template.replace("<<<DOCUMENT_TEXT>>>", text_content)},
        *image_contexts
    ]
    messages.append({"role": "user", "content": user_content})

    # Call OpenAI
    client = OpenAI()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        output = response.choices[0].message.content.strip()

        # Parse JSON (assume LLM outputs clean JSON)
        if output.startswith("```json"):
            output = output.split("```json")[1].split("```")[0].strip()
        extracted_json = json.loads(output)
    except Exception as e:
        print(f"Error extracting from {txt_path.stem}: {e}")
        extracted_json = {h: f"[ERROR: {str(e)}]" for h in headers}

    return extracted_json


def compare_papers_to_excel(
    txt_dir: Union[str, Path],
    template_file: Union[str, Path],
    prompt_file: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None,
    *,
    pdf_names: Optional[Union[str, Iterable[str]]] = None,
    pattern: Optional[str] = None,
    max_files: int = 10,
    delay: float = 1.0
) -> Path:
    """
    Process 1-10 .txt files from papers, extract info using LLM + prompt,
    and populate a comparison Excel file based on the template.

    - Template .xlsx: First row = headers (e.g., Paper, Summary, Key Findings, ...)
    - Adds one row per paper
    - Images (if in same folder as .txt) are used for better extraction

    Args:
        txt_dir: Folder with paper subfolders (each with <name>.txt + optional images)
        template_file: Path to .xlsx template (with headers in row 1)
        prompt_file: Path to .txt prompt (with <<<DOCUMENT_TEXT>>> placeholder)
        output_file: Optional path for output .xlsx (default: comparison_YYYYMMDD_HHMM.xlsx)
        pdf_names: Specific paper names (stems)
        pattern: Glob pattern for filtering
        max_files: Limit to process (default 10)
        delay: Sleep between LLM calls

    Returns:
        Path to saved Excel file
    """
    txt_dir = Path(txt_dir)
    template_file = Path(template_file)
    prompt_file = Path(prompt_file)

    # Validation
    if not txt_dir.exists() or not txt_dir.is_dir():
        raise ValueError(f"Invalid txt_dir: {txt_dir}")
    if not template_file.exists():
        raise FileNotFoundError(f"Template not found: {template_file}")
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_file}")

    # Load template and get headers
    wb = openpyxl.load_workbook(filename=template_file)
    sheet = wb.active
    headers = [cell.value for cell in sheet[1] if cell.value]
    if not headers:
        raise ValueError("Template has no headers in row 1")

    # Default output file
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = txt_dir.parent / f"comparison_{timestamp}.xlsx"
    output_file = Path(output_file)

    # Collect .txt files (same structure as before)
    txt_files = {
        p.parent.name: p
        for p in txt_dir.rglob("*.txt")
        if p.parent.name == p.stem
    }

    if pdf_names:
        if isinstance(pdf_names, str):
            pdf_names = [pdf_names]
        txt_files = {k: v for k, v in txt_files.items() if k in pdf_names}

    if pattern:
        import fnmatch
        txt_files = {k: v for k, v in txt_files.items() if fnmatch.fnmatch(k, pattern)}

    if not txt_files:
        raise ValueError("No .txt files matched")

    # Limit to max_files
    txt_files = dict(list(txt_files.items())[:max_files])
    print(f"Processing {len(txt_files)} paper(s) (limited to {max_files})...\n")

    # Load prompt template
    prompt_template = prompt_file.read_text(encoding="utf-8")

    # Process each paper
    for name, txt_path in tqdm(txt_files.items(), desc="Extracting", unit="paper"):
        info = extract_paper_info(
            txt_path=txt_path,
            headers=headers,
            prompt_template=prompt_template
        )

        # Add row: assume first header is 'Paper' or similar
        row = [name if h.lower() == "paper" else info.get(h, "[N/A]") for h in headers]
        sheet.append(row)

        time.sleep(delay)

    # Save
    wb.save(filename=output_file)
    print(f"\nComparison saved: {output_file}")

    return output_file


# ===================================================================
# EXAMPLE USAGE
# ===================================================================
# ...existing code...

if __name__ == "__main__":
    load_dotenv()

    SCRIPT_DIR = Path(__file__).resolve().parent.parent

    compare_papers_to_excel(
        txt_dir=SCRIPT_DIR / "data/extracted_text/s11042-024-18872-y",  # Fixed path
        template_file=SCRIPT_DIR / "templates/Paper_Comparison_Template.xlsx",  # Fixed path with forward slashes
        prompt_file=SCRIPT_DIR / "prompts/[Prompt]compare_prompt.txt",  # Fixed path with forward slashes
        pdf_names=["s11042-024-18872-y"],  # Just the filename, not the full path
        output_file=SCRIPT_DIR / "data/comparisons/my_comparison.xlsx"
    )