"""
Resume Parser
==============
Parses PDF and DOCX resume files into structured dictionaries.

Strategy:
  - PDF: try pdfplumber first; if extracted text is <20 words, fall back to PyMuPDF (fitz).
  - DOCX: use python-docx to extract paragraphs and tables.

Output format:
  {
      "raw_text": str,
      "tables": [list of list-of-lists],
      "source_file": str (filename only)
  }
"""

import os
from pathlib import Path
from typing import Optional

import pdfplumber
import fitz  # PyMuPDF
from docx import Document


MIN_WORD_COUNT = 20  # Threshold below which we fall back from pdfplumber to PyMuPDF


def parse_pdf_pdfplumber(filepath: str) -> dict:
    """Extract text and tables from a PDF using pdfplumber."""
    text_parts = []
    tables = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)

    raw_text = "\n".join(text_parts).strip()
    return {"raw_text": raw_text, "tables": tables}


def parse_pdf_pymupdf(filepath: str) -> dict:
    """Extract text from a PDF using PyMuPDF (fitz) as fallback."""
    text_parts = []
    doc = fitz.open(filepath)

    for page in doc:
        text_parts.append(page.get_text())

    doc.close()
    raw_text = "\n".join(text_parts).strip()
    # PyMuPDF doesn't natively extract structured tables like pdfplumber,
    # so we return an empty tables list
    return {"raw_text": raw_text, "tables": []}


def parse_pdf(filepath: str) -> dict:
    """
    Parse a PDF file, trying pdfplumber first with PyMuPDF fallback.

    Falls back to PyMuPDF if pdfplumber extracts fewer than MIN_WORD_COUNT words.
    """
    result = parse_pdf_pdfplumber(filepath)
    word_count = len(result["raw_text"].split())

    if word_count < MIN_WORD_COUNT:
        print(f"  [INFO] pdfplumber extracted only {word_count} words from "
              f"{os.path.basename(filepath)}, falling back to PyMuPDF")
        result = parse_pdf_pymupdf(filepath)

    return result


def parse_docx(filepath: str) -> dict:
    """Parse a DOCX file using python-docx."""
    doc = Document(filepath)

    # Extract paragraphs
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    raw_text = "\n".join(paragraphs)

    # Extract tables
    tables = []
    for table in doc.tables:
        table_data = []
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells]
            table_data.append(row_data)
        tables.append(table_data)

    return {"raw_text": raw_text, "tables": tables}


def parse_file(filepath: str) -> dict:
    """
    Parse a resume file (PDF or DOCX) into a structured dict.

    Returns:
        {
            "raw_text": str,
            "tables": list,
            "source_file": str
        }

    Raises:
        ValueError: if the file extension is not supported.
    """
    filepath = str(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)

    if ext == ".pdf":
        result = parse_pdf(filepath)
    elif ext in (".docx", ".doc"):
        result = parse_docx(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext} (file: {filename})")

    result["source_file"] = filename
    return result


def parse_directory(directory: str) -> list:
    """Parse all resume files in a directory."""
    results = []
    directory = Path(directory)

    files = sorted(
        f for f in directory.iterdir()
        if f.suffix.lower() in (".pdf", ".docx", ".doc")
    )

    print(f"Parsing {len(files)} resume files from {directory}...")

    for i, filepath in enumerate(files, 1):
        try:
            result = parse_file(str(filepath))
            results.append(result)
        except Exception as e:
            print(f"  [ERROR] Failed to parse {filepath.name}: {e}")

        if i % 25 == 0:
            print(f"  Parsed {i}/{len(files)} files...")

    print(f"[OK] Successfully parsed {len(results)}/{len(files)} files")
    return results


if __name__ == "__main__":
    import json
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw_resumes")
    results = parse_directory(data_dir)

    # Print a sample
    if results:
        sample = results[0]
        print(f"\nSample parse result for: {sample['source_file']}")
        print(f"  Text length: {len(sample['raw_text'])} chars")
        print(f"  Word count: {len(sample['raw_text'].split())} words")
        print(f"  Tables found: {len(sample['tables'])}")
        print(f"  First 200 chars: {sample['raw_text'][:200]}...")
