import hashlib
import re
from typing import Any, Dict


def validate_input(text: str) -> Dict[str, Any]:
    """
    Validate raw input text and detect special document conditions.
    Distinguishes DOCUMENT_EMPTY, DOCUMENT_REQUIRES_OCR, and INVALID_INPUT.
    """
    if text is None or not text.strip():
        return {
            "status": "INVALID_INPUT",
            "condition": "DOCUMENT_EMPTY",
            "reason": "Document contains no readable text content.",
        }

    # Check for OCR requirement (e.g. placeholder markers from PDF parser or unreadable binary noise)
    stripped = text.strip()
    if stripped.startswith("[OCR_REQUIRED]") or stripped == "%%PDF_IMAGE_ONLY%%":
        return {
            "status": "INVALID_INPUT",
            "condition": "DOCUMENT_REQUIRES_OCR",
            "reason": "Document appears to be an image-only or scanned PDF requiring OCR processing.",
        }

    words = stripped.split()
    if len(words) < 3:
        return {
            "status": "INVALID_INPUT",
            "condition": "SUB_THRESHOLD",
            "reason": "Content contains fewer than 3 words, insufficient for requirements analysis.",
        }

    return {"status": "VALID", "condition": "VALID"}


def classify_content(text: str) -> Dict[str, Any]:
    """
    Advisory classification of content using domain-agnostic heuristics.
    Never acts as a hard filter against messy, informal user notes.
    """
    text_lower = text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Input Type detection
    types_detected = []

    # Check for formal structured_requirements (FR-1, REQ-10, NFR-2)
    if re.search(r'\b(fr-\d+|nfr-\d+|req-\d+|br-\d+)\b', text_lower):
        types_detected.append("structured_requirements")

    # Check for meeting_transcript / dialogue
    if re.search(r'^(?:[A-Za-z0-9\s/]+):\s+', text, re.MULTILINE):
        types_detected.append("meeting_transcript")

    # Check for email headers
    if re.search(r'^from:.*?\nto:.*?\nsubject:', text_lower, re.DOTALL | re.MULTILINE):
        types_detected.append("email")

    # Check for user story document
    if re.search(r'as a\s+.*?\s+i want\s+.*?\s+so that\s+.*?', text_lower):
        types_detected.append("user_story_document")

    # Check for notes (short lines, bullets, fragments)
    bullet_lines = sum(1 for line in lines if line.startswith(('-', '*', '•', '1.', '2.', '3.')))
    if len(lines) > 0 and (bullet_lines / len(lines)) >= 0.3:
        types_detected.append("notes")

    # Check for questions_only
    question_lines = sum(1 for line in lines if line.endswith('?') or re.match(r'^(can|should|what|is|how|could|why)\b', line.lower()))
    if len(lines) > 0 and (question_lines / len(lines)) >= 0.6:
        types_detected.append("questions_only")

    if len(types_detected) == 1:
        input_type = types_detected[0]
    elif len(types_detected) > 1:
        input_type = "mixed_document"
    else:
        input_type = "freeform_text"

    # Signals
    has_explicit_requirements = bool(re.search(r'\b(must|shall|should|can|will|require|allows?|enables?|provides?)\b', text_lower))
    has_actors = bool(re.search(r'\b(user|users|admin|administrator|student|students|customer|customers|employee|employees|doctor|patient|agent|manager|client|developer|analyst)\b', text_lower))
    has_ambiguities = bool(re.search(r'\b(fast|faster|much faster|good|reliable|sometimes|maybe|quick|easy|soon|appropriate|as needed|when available|reasonable|secure|normally|regularly|efficiently|additional time)\b', text_lower))
    has_questions = bool(re.search(r'\?|(?:^|\n)\s*(?:can|should|what|is|how|could|why)\b', text_lower))

    # Metric counts
    req_signals = len(re.findall(r'\b(must|shall|should|require|allows?|enables?|provides?|can)\b', text_lower))
    word_count = len(text.split())
    line_count = len(lines)

    density_ratio = req_signals / max(1, word_count)
    if density_ratio > 0.08:
        requirement_density = "high"
    elif density_ratio > 0.02:
        requirement_density = "medium"
    elif density_ratio > 0.0:
        requirement_density = "low"
    else:
        requirement_density = "none"

    # Quality scoring (advisory)
    # Check if text is completely unrelated/random everyday chatter
    is_chatter = bool(re.search(r'\b(market|bought|apples|weather|groceries|sunny|dinner|cooking|movie|song|trees|birds|lunch|breakfast)\b', text_lower))
    if requirement_density == "none" and not has_explicit_requirements and not has_actors and is_chatter:
        content_quality = "irrelevant"
    elif requirement_density == "high" or (has_explicit_requirements and has_actors):
        content_quality = "rich"
    elif requirement_density == "medium" or has_explicit_requirements or input_type == "notes":
        content_quality = "partial"
    else:
        content_quality = "sparse"

    input_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

    return {
        "status": "VALID",
        "input_type": input_type,
        "content_quality": content_quality,
        "requirement_density": requirement_density,
        "has_explicit_requirements": has_explicit_requirements,
        "has_actors": has_actors,
        "has_ambiguities": has_ambiguities,
        "has_conflicts": False,
        "has_questions": has_questions,
        "word_count": word_count,
        "line_count": line_count,
        "input_hash": f"sha256:{input_hash}",
        "input_preview": text[:200],
    }
