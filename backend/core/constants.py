from __future__ import annotations

ENGINEERING_CATEGORIES: dict[str, str] = {
    "new_infrastructure": "新基建",
    "traditional": "传统基建",
    "urban_renewal": "城市更新",
}

APPLICATION_SCENARIOS: dict[str, str] = {
    "bidding": "招投标",
    "contract": "合同",
}

ALLOWED_FILE_EXTENSIONS: list[str] = [".docx", ".doc", ".pptx", ".xlsx", ".pdf"]


def validate_category(key: str) -> str:
    if key not in ENGINEERING_CATEGORIES:
        raise ValueError(f"Invalid category key: {key}")
    return ENGINEERING_CATEGORIES[key]


def validate_application_scenario(key: str) -> str:
    if key not in APPLICATION_SCENARIOS:
        raise ValueError(f"Invalid application scenario: {key}")
    return APPLICATION_SCENARIOS[key]


def validate_file_type(filename: str) -> str:
    ext = ""
    dot_idx = filename.rfind(".")
    if dot_idx != -1:
        ext = filename[dot_idx:].lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise ValueError(f"Invalid file type: {ext}")
    return ext
