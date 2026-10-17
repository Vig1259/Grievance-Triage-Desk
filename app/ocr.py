from io import BytesIO
from pathlib import Path
import shutil
import fitz
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output
SUPPORTED = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".pdf"}

if not shutil.which("tesseract"):
    tesseract_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tesseract_path.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)

def ocr_image(image):
    image = ImageOps.autocontrast(ImageOps.grayscale(image.convert("RGB")))
    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    confs = []
    for value in data.get("conf", []):
        try:
            value = float(value)
            if value >= 0: confs.append(value)
        except (ValueError, TypeError): pass
    text = pytesseract.image_to_string(image, config="--psm 6").strip()
    return text, (sum(confs) / len(confs) if confs else 0.0)

def extract_text(filename, content):
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported file type {suffix}; use an image or PDF.")
    pages, confs = [], []
    if suffix == ".pdf":
        doc = fitz.open(stream=content, filetype="pdf")
        try:
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                text, conf = ocr_image(Image.open(BytesIO(pix.tobytes("png"))))
                pages.append(text); confs.append(conf)
        finally: doc.close()
    else:
        text, conf = ocr_image(Image.open(BytesIO(content)))
        pages.append(text); confs.append(conf)
    return "\n\n".join(p for p in pages if p).strip(), (sum(confs)/len(confs) if confs else 0.0)
