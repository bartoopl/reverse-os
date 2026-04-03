"""
Stripe payment integrator.
Idempotency key is mandatory — never call without one.
"""
from decimal import Decimal

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from core.config import settings
from integrators.payments.base import PaymentIntegrator, RefundResult, RefundStatus

STRIPE_BASE_URL = "https://api.stripe.com/v1"

# Stripe errors that are safe to retry (network/5xx), vs final failures (4xx card errors)
def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


class StripeIntegrator(PaymentIntegrator):
    provider_name = "stripe"

    def __init__(self) -> None:
        self._secret_key = settings.STRIPE_SECRET_KEY.get_secret_value()

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=STRIPE_BASE_URL,
            auth=(self._secret_key, ""),
            headers={"Stripe-Version": "2024-04-10"},
            timeout=30.0,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception(_is_retryable),
    )
    async def create_refund(
        self,
        original_payment_id: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
        reason: str = "return",
    ) -> RefundResult:
        """
        amount is in major currency units (PLN). Stripe needs minor (grosz).
        idempotency_key MUST already exist in refunds table before calling.
        """
        amount_minor = int(amount * 100)
        stripe_reason = {"return": "requested_by_customer"}.get(reason, "requested_by_customer")

        async with self._client() as client:
            resp = await client.post(
                "/refunds",
                data={
                    "payment_intent": original_payment_id,
                    "amount": amount_minor,
                    "reason": stripe_reason,
                    "metadata[reverseos_idempotency]": idempotency_key,
                },
                headers={"Idempotency-Key": idempotency_key},
            )

            if resp.status_code == 400:
                data = resp.json()
                # Already refunded — idempotent success
                if data.get("error", {}).get("code") == "charge_already_refunded":
                    return RefundResult(
                        provider_refund_id=idempotency_key,
                        status=RefundStatus.SUCCEEDED,
                        amount=amount,
                        currency=currency,
                        raw=data,
                    )

            resp.raise_for_status()
            data = resp.json()

        status_map = {
            "pending": RefundStatus.PENDING,
            "succeeded": RefundStatus.SUCCEEDED,
            "failed": RefundStatus.FAILED,
            "canceled": RefundStatus.FAILED,
        }

        return RefundResult(
            provider_refund_id=data["id"],
            status=status_map.get(data["status"], RefundStatus.PENDING),
            amount=Decimal(data["amount"]) / 100,
            currency=data["currency"].upper(),
            raw=data,
        )

    async def get_refund_status(self, provider_refund_id: str) -> RefundResult:
        async with self._client() as client:
            resp = await client.get(f"/refunds/{provider_refund_id}")
            resp.raise_for_status()
            data = resp.json()

        status_map = {
            "pending": RefundStatus.PENDING,
            "succeeded": RefundStatus.SUCCEEDED,
            "failed": RefundStatus.FAILED,
            "canceled": RefundStatus.FAILED,
        }

        return RefundResult(
            provider_refund_id=data["id"],
            status=status_map.get(data["status"], RefundStatus.PENDING),
            amount=Decimal(data["amount"]) / 100,
            currency=data["currency"].upper(),
            raw=data,
        )
