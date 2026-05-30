from __future__ import annotations

import pytest


@pytest.fixture
def api_headers():
    return {"X-API-Key": "goulong-dev-key"}
