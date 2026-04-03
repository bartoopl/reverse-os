"""Shopify eCommerce integrator."""
import hashlib
import hmac
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from integrators.ecommerce.base import (
    EcommerceIntegrator, OrderNotFound, RemoteCustomer, RemoteOrder, RemoteOrderItem,
)


class ShopifyIntegrator(EcommerceIntegrator):
    platform_name = "shopify"

    def __init__(self) -> None:
        self._api_key = settings.SHOPIFY_API_KEY
        self._api_secret = settings.SHOPIFY_API_SECRET

    def _client(self, shop_domain: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"https://{shop_domain}/admin/api/2024-04",
            headers={
                "X-Shopify-Access-Token": self._api_key.get_secret_value(),
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def fetch_order(self, external_order_id: str) -> RemoteOrder:
        # external_order_id format: "{shop_domain}:{shopify_order_id}"
        shop_domain, order_id = external_order_id.split(":", 1)
        async with self._client(shop_domain) as client:
            resp = await client.get(f"/orders/{order_id}.json")
            if resp.status_code == 404:
                raise OrderNotFound(f"Shopify order {order_id} not found on {shop_domain}")
            resp.raise_for_status()

        data = resp.json()["order"]
        customer_data = data.get("customer", {})

        items = [
            RemoteOrderItem(
                external_id=str(li["id"]),
                sku=li.get("sku") or li.get("variant_id", ""),
                name=li["name"],
                variant=li.get("variant_title"),
                quantity=li["quantity"],
                unit_price_gross=Decimal(li["price"]),
                image_url=None,  # Fetch separately if needed
            )
            for li in data.get("line_items", [])
        ]

        return RemoteOrder(
            external_id=external_order_id,
            platform="shopify",
            order_number=data["name"],
            ordered_at=data["created_at"],
            currency=data["currency"],
            total_gross=Decimal(data["total_price"]),
            total_net=None,  # Shopify doesn't expose net directly
            invoice_ref=None,
            items=items,
            customer=RemoteCustomer(
                external_id=str(customer_data.get("id", "")),
                email=customer_data.get("email", ""),
                name=f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip(),
                phone=customer_data.get("phone"),
            ),
            raw={k: v for k, v in data.items() if k not in ("customer", "billing_address", "shipping_address")},
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def update_order_status(self, external_order_id: str, status: str) -> None:
        shop_domain, order_id = external_order_id.split(":", 1)
        tag_map = {
            "return_approved": "reverse-os:return-approved",
            "return_rejected": "reverse-os:return-rejected",
            "refunded": "reverse-os:refunded",
        }
        tag = tag_map.get(status, f"reverse-os:{status}")
        async with self._client(shop_domain) as client:
            resp = await client.put(
                f"/orders/{order_id}.json",
                json={"order": {"id": order_id, "tags": tag}},
            )
            resp.raise_for_status()

    async def verify_order_token(self, external_order_id: str, token: str) -> bool:
        """HMAC-SHA256 token: sign(secret, order_id)"""
        secret = self._api_secret.get_secret_value().encode()
        expected = hmac.new(secret, external_order_id.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, token)
