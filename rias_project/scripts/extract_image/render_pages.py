import fitz
import os

def render_pdf_pages(pdf_path, output_folder, zoom=4):
    os.makedirs(output_folder, exist_ok=True)
    pdf = fitz.open(pdf_path)
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]

    for page_index in range(len(pdf)):
        page = pdf.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))  # high-res render
        image_filename = f"{pdf_name}_page{page_index + 1}.png"
        pix.save(os.path.join(output_folder, image_filename))
        print(f"✅ Rendered {image_filename}")
    pdf.close()
