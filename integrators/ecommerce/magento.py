"""
Magento 2 REST API integrator.
Używa Bearer token (Integration Token z panelu Magento).
"""
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from integrators.ecommerce.base import (
    EcommerceIntegrator, OrderNotFound, RemoteCustomer, RemoteOrder, RemoteOrderItem,
)


class MagentoIntegrator(EcommerceIntegrator):
    platform_name = "magento"

    def __init__(self) -> None:
        self._base_url = settings.MAGENTO_BASE_URL.rstrip("/")
        self._token = settings.MAGENTO_ACCESS_TOKEN.get_secret_value()

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{self._base_url}/rest/V1",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def fetch_order(self, external_order_id: str) -> RemoteOrder:
        """external_order_id = Magento increment_id (e.g. '000000001')"""
        async with self._client() as client:
            resp = await client.get(f"/orders/{external_order_id}")
            if resp.status_code == 404:
                raise OrderNotFound(f"Magento order {external_order_id} not found")
            resp.raise_for_status()

        data = resp.json()
        billing = data.get("billing_address", {})

        items = [
            RemoteOrderItem(
                external_id=str(item["item_id"]),
                sku=item["sku"],
                name=item["name"],
                variant=None,
                quantity=int(item["qty_ordered"]),
                unit_price_gross=Decimal(str(item["price"])),
                image_url=None,
            )
            for item in data.get("items", [])
            if not item.get("parent_item_id")  # skip configurable children
        ]

        return RemoteOrder(
            external_id=external_order_id,
            platform="magento",
            order_number=data["increment_id"],
            ordered_at=data["created_at"],
            currency=data["order_currency_code"],
            total_gross=Decimal(str(data["grand_total"])),
            total_net=Decimal(str(data.get("subtotal", data["grand_total"]))),
            invoice_ref=data.get("increment_id"),
            items=items,
            customer=RemoteCustomer(
                external_id=str(data.get("customer_id", "")),
                email=data.get("customer_email", ""),
                name=f"{data.get('customer_firstname', '')} {data.get('customer_lastname', '')}".strip(),
                phone=billing.get("telephone"),
            ),
            raw={k: v for k, v in data.items()
                 if k not in ("billing_address", "extension_attributes", "payment")},
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def update_order_status(self, external_order_id: str, status: str) -> None:
        """Add a comment to the Magento order history."""
        comment_map = {
            "return_approved":  "Zwrot zatwierdzony przez REVERSE-OS",
            "return_rejected":  "Zwrot odrzucony przez REVERSE-OS",
            "refunded":         "Refundacja przetworzona przez REVERSE-OS",
        }
        comment = comment_map.get(status, f"REVERSE-OS: {status}")
        async with self._client() as client:
            resp = await client.post(
                f"/orders/{external_order_id}/comments",
                json={
                    "statusHistory": {
                        "comment": comment,
                        "is_customer_notified": 1,
                        "is_visible_on_front": 1,
                    }
                },
            )
            resp.raise_for_status()

    async def verify_order_token(self, external_order_id: str, token: str) -> bool:
        # Token validation delegated to return_tokens table (same as all platforms)
        return True  # actual check done in DB layer
