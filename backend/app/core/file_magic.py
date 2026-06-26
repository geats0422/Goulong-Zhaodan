"""文件 magic bytes 校验 — 防止扩展名伪造"""
from __future__ import annotations

_FILE_SIGNATURES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF-"],
    ".doc": [b"\xd0\xcf\x11\xe0"],
    ".docx": [b"PK\x03\x04"],
    ".pptx": [b"PK\x03\x04"],
    ".xlsx": [b"PK\x03\x04"],
}

_OFFICE_XML_CONTENT_TYPES: dict[str, str] = {
    ".docx": "word/",
    ".pptx": "ppt/",
    ".xlsx": "xl/",
}


def validate_file_magic(filename: str, content: bytes) -> None:
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        return
    ext = filename[dot_idx:].lower()

    if ext == ".txt":
        return

    signatures = _FILE_SIGNATURES.get(ext)
    if signatures is None:
        return

    if not content:
        raise ValueError(f"文件内容为空，无法验证 {ext} 格式")

    matched = any(content.startswith(sig) for sig in signatures)
    if not matched:
        raise ValueError(f"文件内容与扩展名 {ext} 不匹配，疑似伪造")

    if ext in _OFFICE_XML_CONTENT_TYPES and len(content) >= 2000:
        prefix = _OFFICE_XML_CONTENT_TYPES[ext]
        try:
            text_prefix = content[:2000].decode("utf-8", errors="ignore")
        except UnicodeDecodeError:
            return
        if prefix not in text_prefix and "[Content_Types].xml" not in text_prefix:
            raise ValueError(f"文件内容与 {ext} 格式不匹配，疑似伪装为其他 Office 文档")
