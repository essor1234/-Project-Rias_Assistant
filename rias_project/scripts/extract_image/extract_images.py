import fitz
import os

def extract_images_from_pdf(pdf_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    pdf = fitz.open(pdf_path)
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]

    for page_index in range(len(pdf)):
        page = pdf[page_index]
        image_list = page.get_images(full=True)
        print(f"🧩 Page {page_index + 1} has {len(image_list)} images")

        for image_index, img in enumerate(image_list, start=1):
            xref = img[0]
            pix = fitz.Pixmap(pdf, xref)

            # Save the image as RGB
            if pix.n < 5:  # grayscale or RGB
                image_filename = f"{pdf_name}_p{page_index + 1}_img{image_index}.png"
                pix.save(os.path.join(output_folder, image_filename))
            else:
                pix1 = fitz.Pixmap(fitz.csRGB, pix)
                image_filename = f"{pdf_name}_p{page_index + 1}_img{image_index}.png"
                pix1.save(os.path.join(output_folder, image_filename))
                pix1 = None
            pix = None
    pdf.close()
