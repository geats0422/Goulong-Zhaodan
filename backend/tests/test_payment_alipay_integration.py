import importlib.util
from pathlib import Path

from app.api.v1.payments import router

_migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "016_payment_order_method.py"
_spec = importlib.util.spec_from_file_location("migration_016", _migration_path)
assert _spec is not None and _spec.loader is not None
migration_016 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_016)


def test_alipay_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}
    assert "/payment/alipay/page" in paths
    assert "/payment/alipay/notify" in paths


def test_payment_method_migration_links_to_current_head() -> None:
    assert migration_016.revision == "016"
    assert migration_016.down_revision == "015"
