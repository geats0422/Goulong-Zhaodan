from app.services.payment_catalog import PRODUCTS


def test_test_pack_unchanged():
    p = PRODUCTS["test_0_1"]
    assert p.amount_cents == 1
    assert p.token_quota == 10_000


def test_light_pack():
    p = PRODUCTS["light"]
    assert p.amount_cents == 900
    assert p.token_quota == 1_000_000


def test_standard_pack():
    p = PRODUCTS["standard"]
    assert p.amount_cents == 2900
    assert p.token_quota == 5_000_000


def test_large_pack():
    p = PRODUCTS["large"]
    assert p.amount_cents == 8900
    assert p.token_quota == 20_000_000


def test_pro_monthly():
    p = PRODUCTS["pro_monthly"]
    assert p.amount_cents == 6900
    assert p.token_quota == 3_000_000
    assert p.period == "monthly"


def test_pro_quarterly():
    p = PRODUCTS["pro_quarterly"]
    assert p.amount_cents == 17900
    assert p.token_quota == 9_000_000
    assert p.period == "quarterly"


def test_pro_yearly():
    p = PRODUCTS["pro_yearly"]
    assert p.amount_cents == 59900
    assert p.token_quota == 36_000_000
    assert p.period == "yearly"
