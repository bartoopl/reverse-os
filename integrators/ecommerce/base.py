"""
Base interface for all eCommerce integrators.
Add a new platform by subclassing EcommerceIntegrator and registering it.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class RemoteOrder:
    external_id: str
    platform: str
    order_number: str
    ordered_at: str          # ISO 8601
    currency: str
    total_gross: Decimal
    total_net: Decimal | None
    invoice_ref: str | None
    items: list["RemoteOrderItem"]
    customer: "RemoteCustomer"
    raw: dict                # Original platform response (no PII stripped yet)


@dataclass
class RemoteOrderItem:
    external_id: str
    sku: str
    name: str
    variant: str | None
    quantity: int
    unit_price_gross: Decimal
    image_url: str | None


@dataclass
class RemoteCustomer:
    external_id: str
    email: str               # PII - will be encrypted before storage
    name: str | None         # PII
    phone: str | None        # PII


class EcommerceIntegrator(ABC):
    """
    Contract every eCommerce connector must fulfill.
    Each method must be idempotent (safe to retry).
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Unique identifier: 'shopify', 'magento', 'woocommerce'"""
        ...

    @abstractmethod
    async def fetch_order(self, external_order_id: str) -> RemoteOrder:
        """
        Fetch order data from the platform by its external ID.
        Raises OrderNotFound if the order doesn't exist.
        """
        ...

    @abstractmethod
    async def update_order_status(self, external_order_id: str, status: str) -> None:
        """
        Notify the platform that a return has been finalized.
        Status values: 'return_approved', 'return_rejected', 'refunded'
        """
        ...

    @abstractmethod
    async def verify_order_token(self, external_order_id: str, token: str) -> bool:
        """
        Validate a deep-link token for returns.store.com?orderId=X&token=Y
        Returns True if the token is valid for this order.
        """
        ...


class OrderNotFound(Exception):
    pass


class IntegratorRegistry:
    """
    Auto-discovery registry. Register integrators at startup.
    Usage: registry.get('shopify').fetch_order(...)
    """
    _integrators: dict[str, EcommerceIntegrator] = {}

    @classmethod
    def register(cls, integrator: EcommerceIntegrator) -> None:
        cls._integrators[integrator.platform_name] = integrator

    @classmethod
    def get(cls, platform: str) -> EcommerceIntegrator:
        if platform not in cls._integrators:
            raise ValueError(f"No integrator registered for platform: {platform!r}")
        return cls._integrators[platform]

    @classmethod
    def available_platforms(cls) -> list[str]:
        return list(cls._integrators.keys())


ecommerce_registry = IntegratorRegistry()
