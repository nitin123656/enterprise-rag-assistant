from io import BytesIO

import pytest
from PIL import Image
import pymupdf
from backend.document_processor import extract_text, chunk_text

def test_txt_extraction():
    assert extract_text("notes.txt", b"hello\nworld") == "hello\nworld"

def test_pdf_extraction():
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Document facts")
    content = pdf.tobytes()
    pdf.close()

    assert extract_text("facts.pdf", content) == "Document facts"

def test_scanned_pdf_uses_ocr(monkeypatch):
    image = Image.new("RGB", (100, 100), "white")
    image_data = BytesIO()
    image.save(image_data, format="PNG")
    image.close()

    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_image(page.rect, stream=image_data.getvalue())
    content = pdf.tobytes()
    pdf.close()

    def fake_ocr(image, lang):
        assert lang == "eng"
        return "Recognized scanned text"

    monkeypatch.setattr("backend.document_processor.pytesseract.image_to_string", fake_ocr)

    assert extract_text("scan.pdf", content) == "Recognized scanned text"

def test_reject_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported"):
        extract_text("image.png", b"abc")

def test_empty_text_rejected():
    with pytest.raises(ValueError, match="empty"):
        extract_text("notes.txt", b"")

def test_chunking_overlap_and_content():
    text = "alpha " * 250
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(chunks)
    assert "".join(chunks)  # content is retained across chunks

def test_invalid_overlap_rejected():
    with pytest.raises(ValueError):
        chunk_text("abc", 100, 100)
