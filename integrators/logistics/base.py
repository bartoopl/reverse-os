"""Base interface for all logistics/courier integrators."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class LabelFormat(str, Enum):
    PDF = "pdf"
    ZPL = "zpl"
    PNG = "png"


@dataclass
class ShippingLabel:
    tracking_number: str
    label_url: str
    label_format: LabelFormat
    qr_code_url: str | None    # For InPost locker returns
    carrier_data: dict          # Raw carrier response


@dataclass
class TrackingStatus:
    tracking_number: str
    status: str                 # 'in_transit', 'delivered', 'exception'
    location: str | None
    timestamp: str
    raw: dict


class LogisticsIntegrator(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier: 'inpost', 'dhl', 'dpd'"""
        ...

    @abstractmethod
    async def create_return_label(
        self,
        return_id: str,
        recipient_address: dict,   # Already decrypted from PII vault at call site
        package_weight_kg: float,
        idempotency_key: str,      # Golden Rule #1: no duplicate labels
    ) -> ShippingLabel:
        ...

    @abstractmethod
    async def get_tracking_status(self, tracking_number: str) -> TrackingStatus:
        ...

    @abstractmethod
    async def cancel_label(self, tracking_number: str) -> None:
        """Cancel a label that hasn't been scanned yet."""
        ...


class LogisticsRegistry:
    _providers: dict[str, LogisticsIntegrator] = {}

    @classmethod
    def register(cls, provider: LogisticsIntegrator) -> None:
        cls._providers[provider.provider_name] = provider

    @classmethod
    def get(cls, provider: str) -> LogisticsIntegrator:
        if provider not in cls._providers:
            raise ValueError(f"No logistics provider registered: {provider!r}")
        return cls._providers[provider]


logistics_registry = LogisticsRegistry()
