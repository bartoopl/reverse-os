"""
InPost ShipX logistics integrator.
Handles parcel locker (paczkomat) and courier return labels.
"""
import uuid
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from integrators.logistics.base import (
    LabelFormat, LogisticsIntegrator, ShippingLabel, TrackingStatus,
)

SHIPX_BASE_URL = "https://api-shipx-pl.easypack24.net/v1"


class InPostIntegrator(LogisticsIntegrator):
    provider_name = "inpost"

    def __init__(self) -> None:
        self._token = settings.INPOST_API_TOKEN.get_secret_value()

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=SHIPX_BASE_URL,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def create_return_label(
        self,
        return_id: str,
        recipient_address: dict,
        package_weight_kg: float,
        idempotency_key: str,
    ) -> ShippingLabel:
        """
        Creates a return shipment via InPost ShipX API.
        recipient_address keys: name, street, city, postal_code, email, phone
        """
        payload = {
            "service": "inpost_locker_standard",
            "reference": return_id,
            "external_customer_id": idempotency_key,  # ShipX idempotency
            "receiver": {
                "name": recipient_address["name"],
                "email": recipient_address["email"],
                "phone": recipient_address.get("phone", ""),
            },
            "parcels": [{
                "dimensions": {"length": 30, "width": 20, "height": 15, "unit": "mm"},
                "weight": {"amount": package_weight_kg * 1000, "unit": "g"},
            }],
            "cod": None,
            "insurance": None,
        }

        async with self._client() as client:
            # Check idempotency: ShipX uses external_customer_id to deduplicate
            resp = await client.post("/shipments", json=payload)
            if resp.status_code == 409:
                # Already exists — fetch existing by external_customer_id
                search = await client.get(
                    "/shipments", params={"external_customer_id": idempotency_key}
                )
                search.raise_for_status()
                items = search.json().get("items", [])
                if items:
                    return self._parse_shipment(items[0])

            resp.raise_for_status()
            shipment = resp.json()

        # Trigger label generation
        async with self._client() as client:
            label_resp = await client.post(
                f"/shipments/{shipment['id']}/label",
                json={"format": "Pdf", "type": "normal"},
            )
            label_resp.raise_for_status()

        return ShippingLabel(
            tracking_number=shipment["tracking_number"],
            label_url=label_resp.json().get("url", ""),
            label_format=LabelFormat.PDF,
            qr_code_url=shipment.get("qr_code_url"),
            carrier_data={
                "shipment_id": shipment["id"],
                "status": shipment["status"],
                "target_machine": shipment.get("target_machine_id"),
            },
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
    async def get_tracking_status(self, tracking_number: str) -> TrackingStatus:
        async with self._client() as client:
            resp = await client.get(f"/tracking/{tracking_number}")
            resp.raise_for_status()
            data = resp.json()

        status_map = {
            "created": "label_generated",
            "offers_prepared": "label_generated",
            "confirmed": "in_transit",
            "taken_by_courier": "in_transit",
            "adopted_at_source_branch": "in_transit",
            "sent_from_source_branch": "in_transit",
            "adopted_at_sorting_center": "in_transit",
            "sent_from_sorting_center": "in_transit",
            "other_courier_sending": "in_transit",
            "delivered": "received",
            "pickup_reminder_sent": "received",
            "avizo": "received",
            "out_for_delivery": "in_transit",
            "ready_to_pickup": "received",
            "pickup_time_expired": "exception",
            "returned_to_sender": "exception",
            "canceled": "cancelled",
        }

        raw_status = data.get("status", "")
        return TrackingStatus(
            tracking_number=tracking_number,
            status=status_map.get(raw_status, raw_status),
            location=data.get("pickup_machine_id") or data.get("end_of_week_number"),
            timestamp=data.get("updated_at", ""),
            raw=data,
        )

    async def cancel_label(self, tracking_number: str) -> None:
        async with self._client() as client:
            resp = await client.get(
                "/shipments", params={"tracking_number": tracking_number}
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return
            shipment_id = items[0]["id"]
            cancel_resp = await client.delete(f"/shipments/{shipment_id}")
            # 409 = already dispatched, can't cancel — log but don't raise
            if cancel_resp.status_code not in (200, 204, 409):
                cancel_resp.raise_for_status()

    @staticmethod
    def _parse_shipment(data: dict) -> ShippingLabel:
        return ShippingLabel(
            tracking_number=data["tracking_number"],
            label_url=data.get("label_url", ""),
            label_format=LabelFormat.PDF,
            qr_code_url=data.get("qr_code_url"),
            carrier_data={"shipment_id": data["id"], "status": data["status"]},
        )
