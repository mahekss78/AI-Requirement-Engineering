"""
app/utils/helpers.py
====================
Document parsing utilities for the AREA ingestion pipeline.

Responsibility:
  Accept raw binary file content + a file extension, extract all readable
  plain text, and return it normalised (whitespace collapsed, BOM stripped).

Each format has its own parser class that implements DocumentParser.
A factory function `parse_document` selects the correct parser at runtime.

Supported formats (MVP):
  .pdf   — PyPDF2 page-by-page extraction
  .docx  — python-docx paragraph + table extraction
  .xlsx  — openpyxl sheet + cell extraction
  .txt   — UTF-8 plain text
  .eml   — email.parser header + body extraction

Failure behaviour (aligns with PDS Chapter 14 error handling):
  - ParseError is raised for corrupt / unreadable files.
  - EmptyDocumentError is raised when < MIN_WORD_COUNT words are extracted.
  - The ingestion endpoint catches these and marks the document as FAILED.
"""

from __future__ import annotations

import email
import io
import logging
import re
from abc import ABC, abstractmethod

import openpyxl
import PyPDF2
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)

# Minimum word count to treat a document as non-empty
MIN_WORD_COUNT = 10


# ------------------------------------------------------------------ #
# Custom Exceptions
# ------------------------------------------------------------------ #


class ParseError(Exception):
    """Raised when a file cannot be parsed (corrupt, encrypted, wrong format)."""


class EmptyDocumentError(Exception):
    """Raised when the extracted text contains fewer than MIN_WORD_COUNT words."""


# ------------------------------------------------------------------ #
# Abstract Base Parser
# ------------------------------------------------------------------ #


class DocumentParser(ABC):
    """
    All format-specific parsers implement this interface.
    `extract_text` receives the raw bytes and returns a plain-text string.
    """

    @abstractmethod
    def extract_text(self, content: bytes) -> str: ...


# ------------------------------------------------------------------ #
# Format-Specific Parsers
# ------------------------------------------------------------------ #


try:
    import pypdf
except ImportError:
    pypdf = None


class PDFParser(DocumentParser):
    """
    Extracts text from each page of a PDF using pypdf (with PyPDF2 fallback).
    Pages are joined with a newline so paragraph boundaries are preserved.
    Detects scanned / image-only PDFs and raises helpful user guidance.
    """

    def extract_text(self, content: bytes) -> str:
        try:
            pages: list[str] = []
            if pypdf is not None:
                reader = pypdf.PdfReader(io.BytesIO(content))
                if reader.is_encrypted:
                    raise ParseError("PDF is password-protected and cannot be parsed.")
                for page in reader.pages:
                    text = page.extract_text() or ""
                    pages.append(text)
            else:
                reader = PyPDF2.PdfReader(io.BytesIO(content))
                if reader.is_encrypted:
                    raise ParseError("PDF is password-protected and cannot be parsed.")
                for page in reader.pages:
                    text = page.extract_text() or ""
                    pages.append(text)

            extracted = "\n".join(pages).strip()
            word_count = len(extracted.split())

            if word_count == 0:
                raise ParseError("This PDF contains no extractable text. Scanned or image-only PDFs are not supported without OCR. Please upload a searchable text PDF or paste the transcript text directly.")

            return extracted
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(f"PDF extraction failed: {exc}") from exc


class DocxParser(DocumentParser):
    """
    Extracts text from all paragraphs and table cells in a .docx file.
    Tables are rendered as tab-separated rows to preserve structure.
    """

    def extract_text(self, content: bytes) -> str:
        try:
            doc = DocxDocument(io.BytesIO(content))
            lines: list[str] = []

            for para in doc.paragraphs:
                if para.text.strip():
                    lines.append(para.text.strip())

            for table in doc.tables:
                for row in table.rows:
                    cell_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cell_texts:
                        lines.append("\t".join(cell_texts))

            return "\n".join(lines)
        except Exception as exc:
            raise ParseError(f"DOCX extraction failed: {exc}") from exc


class XlsxParser(DocumentParser):
    """
    Extracts text from all cells in all sheets of an .xlsx file.
    Each row is rendered as a tab-separated line.
    """

    def extract_text(self, content: bytes) -> str:
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            lines: list[str] = []
            for sheet in wb.worksheets:
                lines.append(f"[Sheet: {sheet.title}]")
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(cell) for cell in row if cell is not None]
                    if cells:
                        lines.append("\t".join(cells))
            wb.close()
            return "\n".join(lines)
        except Exception as exc:
            raise ParseError(f"XLSX extraction failed: {exc}") from exc


class TxtParser(DocumentParser):
    """Plain-text passthrough with UTF-8 decoding."""

    def extract_text(self, content: bytes) -> str:
        try:
            return content.decode("utf-8", errors="replace")
        except Exception as exc:
            raise ParseError(f"TXT decoding failed: {exc}") from exc


class EmlParser(DocumentParser):
    """
    Extracts the plain-text body from a .eml or .msg email file.
    Falls back to HTML body (stripped of tags) when no plain-text part exists.
    """

    def extract_text(self, content: bytes) -> str:
        try:
            msg = email.message_from_bytes(content)
            parts: list[str] = []

            # Include relevant headers for context
            for header in ("From", "To", "Subject", "Date"):
                value = msg.get(header, "")
                if value:
                    parts.append(f"{header}: {value}")

            # Walk MIME parts for body text
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        parts.append(payload.decode("utf-8", errors="replace"))
                elif ctype == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        raw_html = payload.decode("utf-8", errors="replace")
                        # Strip HTML tags with a simple regex (sufficient for MVP)
                        clean = re.sub(r"<[^>]+>", " ", raw_html)
                        parts.append(clean)

            return "\n".join(parts)
        except Exception as exc:
            raise ParseError(f"EML extraction failed: {exc}") from exc


# ------------------------------------------------------------------ #
# Normalizer
# ------------------------------------------------------------------ #


def normalize_text(raw: str) -> str:
    """
    Post-process extracted text:
    - Strip Unicode BOM and zero-width characters.
    - Collapse consecutive whitespace to a single space within lines.
    - Remove completely blank lines (keep single blank lines for readability).
    - Strip leading/trailing whitespace.
    """
    # Remove BOM and zero-width chars
    raw = raw.replace("\ufeff", "").replace("\u200b", "")

    # Normalize line endings
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse internal whitespace on each line
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.split("\n")]

    # Remove runs of more than one blank line
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = line == ""
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank

    return "\n".join(cleaned).strip()


# ------------------------------------------------------------------ #
# Parser Factory
# ------------------------------------------------------------------ #

_PARSER_MAP: dict[str, type[DocumentParser]] = {
    ".pdf":  PDFParser,
    ".docx": DocxParser,
    ".xlsx": XlsxParser,
    ".txt":  TxtParser,
    ".eml":  EmlParser,
    ".msg":  EmlParser,  # .msg can be parsed as raw email bytes
}

SUPPORTED_EXTENSIONS = set(_PARSER_MAP.keys())


def parse_document(file_name: str, content: bytes) -> tuple[str, int]:
    """
    Parse a document and return (normalized_text, word_count).

    Args:
        file_name: Original filename including extension (e.g. "notes.pdf").
        content:   Raw binary file content.

    Returns:
        A tuple of (normalized plain text, word count).

    Raises:
        ParseError:         File cannot be parsed.
        EmptyDocumentError: Extracted text has fewer than MIN_WORD_COUNT words.
        ValueError:         File extension is not supported.
    """
    ext = _get_extension(file_name)
    if ext not in _PARSER_MAP:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    parser_cls = _PARSER_MAP[ext]
    parser = parser_cls()

    logger.info(f"Parsing '{file_name}' with {parser_cls.__name__}")
    raw_text = parser.extract_text(content)
    normalized = normalize_text(raw_text)

    word_count = len(normalized.split())
    logger.info(f"Extracted {word_count} words from '{file_name}'")

    if word_count < MIN_WORD_COUNT:
        raise EmptyDocumentError(
            f"Document '{file_name}' yielded only {word_count} words "
            f"(minimum required: {MIN_WORD_COUNT}). "
            "Please upload a document with substantive content."
        )

    return normalized, word_count


def _get_extension(file_name: str) -> str:
    """Extract the lowercase file extension including the dot."""
    parts = file_name.rsplit(".", 1)
    if len(parts) < 2:
        return ""
    return f".{parts[-1].lower()}"


def parse_document_content(file_content_b64: str, file_name: str) -> str:
    """
    Decodes Base64 file content and parses plain text using parse_document.
    Falls back gracefully if base64 or parsing fails.
    """
    import base64
    if not file_content_b64:
        return f"Ingested content from {file_name}"

    try:
        raw_bytes = base64.b64decode(file_content_b64)
        normalized_text, _ = parse_document(file_name, raw_bytes)
        return normalized_text
    except Exception as exc:
        logger.warning(f"parse_document_content fallback for '{file_name}': {exc}")
        try:
            raw_bytes = base64.b64decode(file_content_b64)
            return raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            return f"Ingested text content from {file_name}"

