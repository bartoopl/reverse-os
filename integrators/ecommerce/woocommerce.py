"""
WooCommerce REST API v3 integrator.
Używa Basic Auth z Consumer Key + Consumer Secret.
"""
import hmac
import hashlib
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from integrators.ecommerce.base import (
    EcommerceIntegrator, OrderNotFound, RemoteCustomer, RemoteOrder, RemoteOrderItem,
)


class WooCommerceIntegrator(EcommerceIntegrator):
    platform_name = "woocommerce"

    def __init__(self, site_url: str, consumer_key: str, consumer_secret: str) -> None:
        self._site_url = site_url.rstrip("/")
        self._ck = consumer_key
        self._cs = consumer_secret

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{self._site_url}/wp-json/wc/v3",
            auth=(self._ck, self._cs),
            timeout=15.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def fetch_order(self, external_order_id: str) -> RemoteOrder:
        async with self._client() as client:
            resp = await client.get(f"/orders/{external_order_id}")
            if resp.status_code == 404:
                raise OrderNotFound(f"WooCommerce order {external_order_id} not found")
            resp.raise_for_status()

        data = resp.json()
        billing = data.get("billing", {})

        items = [
            RemoteOrderItem(
                external_id=str(item["id"]),
                sku=item.get("sku", str(item["product_id"])),
                name=item["name"],
                variant=item.get("variation_id") and str(item["variation_id"]) or None,
                quantity=item["quantity"],
                unit_price_gross=Decimal(str(item["price"])),
                image_url=None,
            )
            for item in data.get("line_items", [])
        ]

        return RemoteOrder(
            external_id=external_order_id,
            platform="woocommerce",
            order_number=str(data["number"]),
            ordered_at=data["date_created"],
            currency=data["currency"],
            total_gross=Decimal(str(data["total"])),
            total_net=Decimal(str(data.get("total", data["total"]))),
            invoice_ref=None,
            items=items,
            customer=RemoteCustomer(
                external_id=str(data.get("customer_id", "")),
                email=billing.get("email", ""),
                name=f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
                phone=billing.get("phone"),
            ),
            raw={k: v for k, v in data.items()
                 if k not in ("billing", "shipping", "_links")},
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def update_order_status(self, external_order_id: str, status: str) -> None:
        woo_status_map = {
            "return_approved": "processing",
            "refunded":        "refunded",
            "return_rejected": "completed",
        }
        woo_status = woo_status_map.get(status, "completed")
        async with self._client() as client:
            resp = await client.put(
                f"/orders/{external_order_id}",
                json={"status": woo_status},
            )
            resp.raise_for_status()

    async def verify_order_token(self, external_order_id: str, token: str) -> bool:
        return True  # DB layer handles token verification
