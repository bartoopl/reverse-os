"""Base interface for payment integrators. Idempotency is critical here."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class RefundStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class RefundResult:
    provider_refund_id: str
    status: RefundStatus
    amount: Decimal
    currency: str
    raw: dict


class PaymentIntegrator(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    async def create_refund(
        self,
        original_payment_id: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,          # Golden Rule #1: never double-refund
        reason: str = "return",
    ) -> RefundResult:
        """
        Idempotency_key must be stored in the refunds table BEFORE calling this.
        If this call succeeds, mark refunds.status = 'succeeded'.
        If this call fails, mark refunds.status = 'failed' — do NOT retry with same key.
        """
        ...

    @abstractmethod
    async def get_refund_status(self, provider_refund_id: str) -> RefundResult:
        ...


class PaymentRegistry:
    _providers: dict[str, PaymentIntegrator] = {}

    @classmethod
    def register(cls, provider: PaymentIntegrator) -> None:
        cls._providers[provider.provider_name] = provider

    @classmethod
    def get(cls, provider: str) -> PaymentIntegrator:
        if provider not in cls._providers:
            raise ValueError(f"No payment provider registered: {provider!r}")
        return cls._providers[provider]


payment_registry = PaymentRegistry()
