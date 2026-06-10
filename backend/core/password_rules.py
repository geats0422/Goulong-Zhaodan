from __future__ import annotations

import json
from pathlib import Path

_ALLOWED_SPECIAL = set("!@#$%^&*()_-+=[]{}|:;<>,.?/~")
_WEAK_PASSWORDS: set[str] | None = None


def _load_weak_passwords() -> set[str]:
    global _WEAK_PASSWORDS
    if _WEAK_PASSWORDS is not None:
        return _WEAK_PASSWORDS
    p = Path(__file__).parent / "weak_passwords.json"
    with p.open(encoding="utf-8") as f:
        _WEAK_PASSWORDS = {w.lower() for w in json.load(f)}
    return _WEAK_PASSWORDS


def validate_password(password: str) -> list[str]:
    errors: list[str] = []

    if len(password) < 8:
        errors.append("密码长度不能少于 8 位")
    if len(password) > 128:
        errors.append("密码长度不能超过 128 位")

    if " " in password:
        errors.append("密码不能包含空格")

    if any(ord(c) > 127 for c in password):
        errors.append("密码只能包含 ASCII 字符")

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)

    if not has_upper:
        errors.append("密码必须包含至少一个大写字母")
    if not has_lower:
        errors.append("密码必须包含至少一个小写字母")
    if not has_digit:
        errors.append("密码必须包含至少一个数字")

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") | _ALLOWED_SPECIAL
    invalid_chars = set(password) - allowed
    if invalid_chars:
        errors.append(f"密码包含不允许的字符: {''.join(sorted(invalid_chars))}")

    weak = _load_weak_passwords()
    if password.lower() in weak:
        errors.append("该密码过于常见，请选择更安全的密码")

    return errors
