from __future__ import annotations

from pathlib import Path

from markitdown import MarkItDown


class ConversionError(Exception):
    pass


def convert_to_markdown(file_path: str | Path) -> str:
    path = Path(file_path)
    if not path.exists():
        raise ConversionError(f"File not found: {path}")
    try:
        md = MarkItDown()
        result = md.convert(str(path))
    except Exception as exc:
        raise ConversionError(str(exc)) from exc
    text = result.text_content
    if not text or not text.strip():
        raise ConversionError("Conversion produced empty content")
    return text
