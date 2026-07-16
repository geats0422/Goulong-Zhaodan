from __future__ import annotations

from collections.abc import MutableMapping

OFFICIAL_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL_NAME = "deepseek-v4-pro"

MODEL_CATALOG = [
    {"model_name": "deepseek-v4-pro", "label": "DeepSeek V4 Pro", "tier": "高准确度 · 慢", "context": "128K"},
    {"model_name": "deepseek-v4-flash", "label": "DeepSeek V4 Flash", "tier": "快速响应", "context": "64K"},
]


def normalize_model_name(model_name: str | None) -> str | None:
    if model_name and model_name.startswith("deepseek-ai/"):
        return model_name.removeprefix("deepseek-ai/")
    return model_name


def configure_openai_environment(
    environ: MutableMapping[str, str], *, api_key: str, base_url: str
) -> None:
    environ["OPENAI_API_KEY"] = api_key
    if base_url:
        environ["OPENAI_API_BASE"] = base_url


def validate_official_deepseek_configuration(base_url: str, model_name: str) -> None:
    if base_url.rstrip("/") != OFFICIAL_DEEPSEEK_BASE_URL:
        raise RuntimeError("生产环境必须使用 DeepSeek 官方 API")
    allowed = {item["model_name"] for item in MODEL_CATALOG}
    if normalize_model_name(model_name) not in allowed:
        raise RuntimeError("生产环境必须使用官方 DeepSeek 模型名")
