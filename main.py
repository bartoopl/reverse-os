"""REVERSE-OS FastAPI application entry point."""
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.v1.endpoints import auth, orders, returns, webhooks
from api.v1.endpoints.admin import auth as admin_auth, financial as admin_financial, ksef as admin_ksef, returns as admin_returns, rules as admin_rules, stats as admin_stats, users as admin_users
from core.config import settings
from integrators.ecommerce.base import ecommerce_registry
from integrators.logistics.base import logistics_registry
from integrators.payments.base import payment_registry

log = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="REVERSE-OS",
        description="Open-Core Returns Management System",
        version="0.1.0",
        docs_url="/docs" if settings.APP_ENV != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.APP_ENV == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register integrators
    _register_integrators()

    # Mount routers
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(orders.router, prefix="/api/v1")
    app.include_router(returns.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")
    # Admin
    app.include_router(admin_auth.router, prefix="/api/v1")
    app.include_router(admin_stats.router, prefix="/api/v1")
    app.include_router(admin_returns.router, prefix="/api/v1")
    app.include_router(admin_rules.router, prefix="/api/v1")
    app.include_router(admin_financial.router, prefix="/api/v1")
    app.include_router(admin_users.router, prefix="/api/v1")
    app.include_router(admin_ksef.router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "platforms": ecommerce_registry.available_platforms(),
            "enterprise": settings.is_enterprise,
        }

    return app


def _register_integrators() -> None:
    # eCommerce
    if settings.SHOPIFY_API_KEY:
        from integrators.ecommerce.shopify import ShopifyIntegrator
        ecommerce_registry.register(ShopifyIntegrator())
        log.info("integrator.registered", type="ecommerce", name="shopify")

    if settings.MAGENTO_BASE_URL and settings.MAGENTO_ACCESS_TOKEN:
        from integrators.ecommerce.magento import MagentoIntegrator
        ecommerce_registry.register(MagentoIntegrator())
        log.info("integrator.registered", type="ecommerce", name="magento")

    # WooCommerce: multi-tenant, registered per-store via admin

    # Logistics
    if settings.INPOST_API_TOKEN:
        from integrators.logistics.inpost import InPostIntegrator
        logistics_registry.register(InPostIntegrator())
        log.info("integrator.registered", type="logistics", name="inpost")

    # Payments
    if settings.STRIPE_SECRET_KEY:
        from integrators.payments.stripe import StripeIntegrator
        payment_registry.register(StripeIntegrator())
        log.info("integrator.registered", type="payment", name="stripe")

    if settings.PAYU_CLIENT_ID and settings.PAYU_CLIENT_SECRET:
        from integrators.payments.payu import PayUIntegrator
        payment_registry.register(PayUIntegrator())
        log.info("integrator.registered", type="payment", name="payu")


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.APP_ENV == "development")
