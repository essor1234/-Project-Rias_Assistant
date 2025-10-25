import os
import fitz
from pathlib import Path

def extract_images_from_pdf(pdf_path: str, output_folder: str) -> None:
    """Extract all images from a PDF file."""
    doc = fitz.open(pdf_path)
    
    for page_num, page in enumerate(doc, start=1):
        image_list = page.get_images()
        
        for img_idx, img in enumerate(image_list, start=1):
            xref = img[0]
            base_image = doc.extract_image(xref)
            
            try:
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Use JPEG instead of PNG for problematic images
                if image_ext.lower() == "png":
                    image_ext = "jpg"
                
                image_filename = f"page{page_num}_img{img_idx}.{image_ext}"
                with open(os.path.join(output_folder, image_filename), "wb") as img_file:
                    img_file.write(image_bytes)
                    
            except ValueError as e:
                print(f"Warning: Could not save image {img_idx} from page {page_num}: {e}")
                continue
                
    doc.close()