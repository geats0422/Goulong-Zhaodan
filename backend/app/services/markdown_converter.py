from __future__ import annotations

import zipfile
from pathlib import Path
from struct import unpack_from
from typing import TypedDict
from xml.etree import ElementTree

from markitdown import MarkItDown


class ConversionError(Exception):
    pass


END_OF_CHAIN = 0xFFFFFFFE
FREE_SECTOR = 0xFFFFFFFF
NO_STREAM = 0xFFFFFFFF


class _DirectoryEntry(TypedDict):
    name: str
    type: int
    start: int
    size: int


def convert_to_markdown(file_path: str | Path) -> str:
    path = Path(file_path)
    if not path.exists():
        raise ConversionError(f"File not found: {path}")
    if path.suffix.lower() == ".docx":
        fallback_text = _convert_docx_to_text(path)
        if fallback_text.strip():
            return fallback_text
    if path.suffix.lower() == ".doc":
        fallback_text = _convert_doc_to_text(path)
        if fallback_text.strip():
            return fallback_text
    if path.suffix.lower() == ".pdf":
        fallback_text = _convert_pdf_to_text(path)
        if fallback_text.strip():
            return fallback_text
    try:
        md = MarkItDown()
        result = md.convert(str(path))
    except Exception as exc:
        raise ConversionError(str(exc)) from exc
    text = result.text_content
    if not text or not text.strip():
        raise ConversionError("Conversion produced empty content")
    return text


def _convert_docx_to_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile, OSError):
        return ""

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError:
        return ""

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{namespace}p"):
        parts = [node.text or "" for node in paragraph.iter(f"{namespace}t")]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _convert_pdf_to_text(path: Path) -> str:
    try:
        import fitz
    except ImportError:
        return ""
    try:
        doc = fitz.open(str(path))
    except Exception:
        return ""
    pages: list[str] = []
    for page in doc:
        text = page.get_text()
        if text:
            pages.append(text)
    doc.close()
    return "\n\n".join(pages).strip()


def _convert_doc_to_text(path: Path) -> str:
    try:
        compound_file = _CompoundFile(path.read_bytes())
        word_document = compound_file.open_stream("WordDocument")
    except (OSError, ValueError, KeyError):
        return ""

    if len(word_document) < 0x01AA:
        return ""

    flags = unpack_from("<H", word_document, 0x0A)[0]
    table_stream_name = "1Table" if flags & 0x0200 else "0Table"
    try:
        table_stream = compound_file.open_stream(table_stream_name)
    except KeyError:
        return _extract_readable_text_from_binary(word_document)

    fc_clx = unpack_from("<I", word_document, 0x01A2)[0]
    lcb_clx = unpack_from("<I", word_document, 0x01A6)[0]
    if not lcb_clx or fc_clx + lcb_clx > len(table_stream):
        return _extract_readable_text_from_binary(word_document)

    text = _extract_word_piece_table_text(word_document, table_stream[fc_clx : fc_clx + lcb_clx])
    return text or _extract_readable_text_from_binary(word_document)


def _extract_word_piece_table_text(word_document: bytes, clx: bytes) -> str:
    offset = 0
    piece_table = b""
    while offset < len(clx):
        marker = clx[offset]
        offset += 1
        if marker == 0x01:
            if offset + 2 > len(clx):
                return ""
            skip = unpack_from("<H", clx, offset)[0]
            offset += 2 + skip
        elif marker == 0x02:
            if offset + 4 > len(clx):
                return ""
            size = unpack_from("<I", clx, offset)[0]
            offset += 4
            piece_table = clx[offset : offset + size]
            break
        else:
            break

    if len(piece_table) < 16:
        return ""
    piece_count = (len(piece_table) - 4) // 12
    if piece_count <= 0:
        return ""

    cp_offsets = [unpack_from("<I", piece_table, index * 4)[0] for index in range(piece_count + 1)]
    pcd_offset = (piece_count + 1) * 4
    paragraphs: list[str] = []
    for index in range(piece_count):
        char_count = cp_offsets[index + 1] - cp_offsets[index]
        if char_count <= 0:
            continue
        pcd = piece_table[pcd_offset + index * 8 : pcd_offset + (index + 1) * 8]
        if len(pcd) < 8:
            continue
        encoded_fc = unpack_from("<I", pcd, 2)[0]
        compressed = bool(encoded_fc & 0x40000000)
        fc = encoded_fc & 0x3FFFFFFF
        if compressed:
            raw = word_document[fc // 2 : fc // 2 + char_count]
            text = raw.decode("cp1252", errors="ignore")
        else:
            raw = word_document[fc : fc + char_count * 2]
            text = raw.decode("utf-16le", errors="ignore")
        cleaned = _clean_extracted_doc_text(text)
        if cleaned:
            paragraphs.append(cleaned)
    return "\n\n".join(paragraphs)


def _extract_readable_text_from_binary(data: bytes) -> str:
    text = data.decode("utf-16le", errors="ignore")
    return _clean_extracted_doc_text(text)


def _clean_extracted_doc_text(text: str) -> str:
    text = text.replace("\r", "\n")
    lines = []
    for line in text.splitlines():
        cleaned = "".join(ch for ch in line if ch == "\t" or ch == " " or ch == "\n" or ord(ch) >= 32).strip()
        if cleaned and _readable_score(cleaned) >= 0.45:
            lines.append(cleaned)
    return "\n".join(lines).strip()


def _readable_score(text: str) -> float:
    if not text:
        return 0.0
    readable = sum(ch.isalnum() or ch.isspace() or "\u4e00" <= ch <= "\u9fff" or ch in "，。；：、（）《》【】“”！？-—_" for ch in text)
    return readable / len(text)


class _CompoundFile:
    def __init__(self, data: bytes) -> None:
        if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ValueError("not an OLE compound file")
        self.data = data
        self.sector_size = 1 << unpack_from("<H", data, 30)[0]
        self.mini_sector_size = 1 << unpack_from("<H", data, 32)[0]
        self.mini_cutoff = unpack_from("<I", data, 56)[0]
        self.first_dir_sector = unpack_from("<I", data, 48)[0]
        self.first_mini_fat_sector = unpack_from("<I", data, 60)[0]
        self.mini_fat_sector_count = unpack_from("<I", data, 64)[0]
        self.fat = self._read_fat()
        self.directory_entries = self._read_directory_entries()
        self.root_entry = next((entry for entry in self.directory_entries if entry["type"] == 5), None)
        self.mini_fat = self._read_mini_fat()
        self.mini_stream = self._read_regular_stream(self.root_entry["start"], self.root_entry["size"]) if self.root_entry else b""

    def open_stream(self, name: str) -> bytes:
        entry = next((item for item in self.directory_entries if item["name"] == name), None)
        if entry is None:
            raise KeyError(name)
        if entry["size"] < self.mini_cutoff and self.mini_fat:
            return self._read_mini_stream(entry["start"], entry["size"])
        return self._read_regular_stream(entry["start"], entry["size"])

    def _sector_offset(self, sector_id: int) -> int:
        return 512 + sector_id * self.sector_size

    def _read_sector(self, sector_id: int) -> bytes:
        offset = self._sector_offset(sector_id)
        return self.data[offset : offset + self.sector_size]

    def _read_fat(self) -> list[int]:
        fat_sector_ids = [
            unpack_from("<I", self.data, 76 + index * 4)[0]
            for index in range(109)
            if unpack_from("<I", self.data, 76 + index * 4)[0] not in (FREE_SECTOR, END_OF_CHAIN)
        ]
        fat: list[int] = []
        for sector_id in fat_sector_ids:
            sector = self._read_sector(sector_id)
            fat.extend(unpack_from(f"<{self.sector_size // 4}I", sector))
        return fat

    def _sector_chain(self, start_sector: int) -> list[int]:
        if start_sector in (NO_STREAM, END_OF_CHAIN, FREE_SECTOR):
            return []
        chain = []
        current = start_sector
        seen: set[int] = set()
        while current not in (END_OF_CHAIN, FREE_SECTOR, NO_STREAM) and current < len(self.fat) and current not in seen:
            seen.add(current)
            chain.append(current)
            current = self.fat[current]
        return chain

    def _read_regular_stream(self, start_sector: int, size: int) -> bytes:
        chunks = [self._read_sector(sector_id) for sector_id in self._sector_chain(start_sector)]
        return b"".join(chunks)[:size]

    def _read_directory_entries(self) -> list[_DirectoryEntry]:
        directory_stream = self._read_regular_stream(self.first_dir_sector, 2**31)
        entries: list[_DirectoryEntry] = []
        for offset in range(0, len(directory_stream), 128):
            entry = directory_stream[offset : offset + 128]
            if len(entry) < 128:
                continue
            name_length = unpack_from("<H", entry, 64)[0]
            if name_length < 2:
                continue
            name = entry[: name_length - 2].decode("utf-16le", errors="ignore")
            entries.append(
                {
                    "name": name,
                    "type": entry[66],
                    "start": unpack_from("<I", entry, 116)[0],
                    "size": unpack_from("<Q", entry, 120)[0],
                }
            )
        return entries

    def _read_mini_fat(self) -> list[int]:
        if self.first_mini_fat_sector in (NO_STREAM, END_OF_CHAIN, FREE_SECTOR) or self.mini_fat_sector_count == 0:
            return []
        data = b"".join(self._read_sector(sector_id) for sector_id in self._sector_chain(self.first_mini_fat_sector))
        return list(unpack_from(f"<{len(data) // 4}I", data)) if data else []

    def _read_mini_stream(self, start_sector: int, size: int) -> bytes:
        chunks = []
        current = start_sector
        seen: set[int] = set()
        while current not in (END_OF_CHAIN, FREE_SECTOR, NO_STREAM) and current < len(self.mini_fat) and current not in seen:
            seen.add(current)
            offset = current * self.mini_sector_size
            chunks.append(self.mini_stream[offset : offset + self.mini_sector_size])
            current = self.mini_fat[current]
        return b"".join(chunks)[:size]
