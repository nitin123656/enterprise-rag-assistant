from pathlib import Path
from io import BytesIO
import shutil
from PIL import Image
import pymupdf
import pytesseract
from langchain_text_splitters import RecursiveCharacterTextSplitter

ALLOWED_EXTENSIONS = {".pdf", ".txt"}

def _configure_tesseract() -> None:
    if shutil.which(pytesseract.pytesseract.tesseract_cmd):
        return

    for path in (
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ):
        if path.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(path)
            return

def extract_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Upload a PDF or TXT file.")
    if not content:
        raise ValueError("The uploaded file is empty.")

    if ext == ".txt":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("TXT files must be UTF-8 encoded.") from exc
    else:
        try:
            with pymupdf.open(stream=content, filetype="pdf") as pdf:
                page_texts = []
                for page in pdf:
                    page_text = page.get_text("text").strip()
                    if not page_text:
                        try:
                            image_data = page.get_pixmap(dpi=300).tobytes("png")
                            with Image.open(BytesIO(image_data)) as image:
                                _configure_tesseract()
                                page_text = pytesseract.image_to_string(image, lang="eng").strip()
                        except pytesseract.TesseractNotFoundError as exc:
                            raise RuntimeError(
                                "Tesseract OCR is required to process scanned PDFs. "
                                "Install Tesseract OCR and ensure it is available on PATH."
                            ) from exc
                    page_texts.append(page_text)
                text = "\n".join(page_texts)
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise ValueError("Could not read this PDF. It may be corrupt or encrypted.") from exc

    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not text:
        raise ValueError("No text could be extracted from the PDF, including with OCR.")
    return text

def chunk_text(text: str, chunk_size: int = 600, chunk_overlap: int = 100) -> list[str]:
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("Require chunk_size > chunk_overlap >= 0.")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )
    return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]
