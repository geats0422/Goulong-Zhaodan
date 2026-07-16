from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


def test_document_job_retry_rate_limit_config_defaults() -> None:
    config = Settings(_env_file=None)

    assert config.document_job_retry_rate_limit == 5
    assert config.document_job_retry_rate_limit_window == 3600


def test_both_env_examples_document_retry_rate_limit_settings() -> None:
    backend_dir = Path(__file__).resolve().parents[1]

    for filename in (".env.example", "env.example"):
        contents = (backend_dir / filename).read_text(encoding="utf-8")
        assert "DOCUMENT_JOB_RETRY_RATE_LIMIT=5" in contents
        assert "DOCUMENT_JOB_RETRY_RATE_LIMIT_WINDOW=3600" in contents
