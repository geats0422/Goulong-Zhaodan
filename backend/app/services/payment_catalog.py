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
    "light": Product(
        code="light",
        name="轻量包",
        product_type="addon",
        amount_cents=500,
        token_quota=1_000_000,
        period="addon",
        free_user_allowed=True,
    ),
    "standard": Product(
        code="standard",
        name="标准包",
        product_type="addon",
        amount_cents=1800,
        token_quota=5_000_000,
        period="addon",
        free_user_allowed=True,
    ),
    "large": Product(
        code="large",
        name="大额包",
        product_type="addon",
        amount_cents=5800,
        token_quota=20_000_000,
        period="addon",
        free_user_allowed=False,
    ),
    "pro_monthly": Product(
        code="pro_monthly",
        name="Pro 月度订阅",
        product_type="subscription",
        amount_cents=4900,
        token_quota=2_000_000,
        period="monthly",
        free_user_allowed=False,
    ),
    "pro_quarterly": Product(
        code="pro_quarterly",
        name="Pro 季度订阅",
        product_type="subscription",
        amount_cents=13900,
        token_quota=6_000_000,
        period="quarterly",
        free_user_allowed=False,
    ),
    "pro_yearly": Product(
        code="pro_yearly",
        name="Pro 年度订阅",
        product_type="subscription",
        amount_cents=49900,
        token_quota=24_000_000,
        period="yearly",
        free_user_allowed=False,
    ),
}


def get_product(code: str) -> Product | None:
    return PRODUCTS.get(code)


def is_addon(code: str) -> bool:
    product = PRODUCTS.get(code)
    return product is not None and product.product_type == "addon"
