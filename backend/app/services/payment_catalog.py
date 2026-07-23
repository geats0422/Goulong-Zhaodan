from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    code: str
    name: str
    product_type: str  # "addon" | "subscription"
    amount_cents: int
    token_quota: int
    period: str  # "monthly" | "quarterly" | "yearly" | "addon"
    free_user_allowed: bool = True


PRODUCTS: dict[str, Product] = {
    "test_0_1": Product(
        code="test_0_1",
        name="支付测试包",
        product_type="addon",
        amount_cents=1,
        token_quota=10_000,
        period="addon",
        free_user_allowed=True,
    ),
    "light": Product(
        code="light",
        name="轻量包",
        product_type="addon",
        amount_cents=900,
        token_quota=1_000_000,
        period="addon",
        free_user_allowed=True,
    ),
    "standard": Product(
        code="standard",
        name="标准包",
        product_type="addon",
        amount_cents=2900,
        token_quota=5_000_000,
        period="addon",
        free_user_allowed=True,
    ),
    "large": Product(
        code="large",
        name="大额包",
        product_type="addon",
        amount_cents=8900,
        token_quota=20_000_000,
        period="addon",
        free_user_allowed=False,
    ),
    "pro_monthly": Product(
        code="pro_monthly",
        name="Pro 月度订阅",
        product_type="subscription",
        amount_cents=6900,
        token_quota=3_000_000,
        period="monthly",
        free_user_allowed=False,
    ),
    "pro_quarterly": Product(
        code="pro_quarterly",
        name="Pro 季度订阅",
        product_type="subscription",
        amount_cents=17900,
        token_quota=9_000_000,
        period="quarterly",
        free_user_allowed=False,
    ),
    "pro_yearly": Product(
        code="pro_yearly",
        name="Pro 年度订阅",
        product_type="subscription",
        amount_cents=59900,
        token_quota=36_000_000,
        period="yearly",
        free_user_allowed=False,
    ),
}


def get_product(code: str) -> Product | None:
    return PRODUCTS.get(code)


def is_addon(code: str) -> bool:
    product = PRODUCTS.get(code)
    return product is not None and product.product_type == "addon"
