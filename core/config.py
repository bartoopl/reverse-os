from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn, SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: SecretStr
    LICENSE_KEY: str | None = None         # Enterprise feature gate

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # PII Vault encryption key (AES-256, base64 encoded)
    PII_ENCRYPTION_KEY: SecretStr

    # Redis / Queue
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"  # type: ignore

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Integrations - eCommerce
    SHOPIFY_API_KEY: SecretStr | None = None
    SHOPIFY_API_SECRET: SecretStr | None = None
    MAGENTO_BASE_URL: str | None = None
    MAGENTO_ACCESS_TOKEN: SecretStr | None = None

    # Integrations - Logistics
    INPOST_API_TOKEN: SecretStr | None = None
    DHL_API_KEY: SecretStr | None = None

    # Integrations - Payments
    STRIPE_SECRET_KEY: SecretStr | None = None
    STRIPE_WEBHOOK_SECRET: SecretStr | None = None
    PAYU_CLIENT_ID: str | None = None
    PAYU_CLIENT_SECRET: SecretStr | None = None

    # Company / KSeF
    COMPANY_NAME: str = "REVERSE-OS Sp. z o.o."
    COMPANY_NIP: str = "0000000000"
    COMPANY_ADDRESS: str = ""
    ERP_WEBHOOK_URL: str | None = None     # POST target for KSeF correction invoices

    # Feature flags
    ENABLE_RULE_ENGINE: bool = True
    ENABLE_AUTO_REFUND: bool = False       # Requires Enterprise license
    MAX_FREE_RETURNS_PER_MONTH: int = 100  # Open-core limit

    @property
    def is_enterprise(self) -> bool:
        return self.LICENSE_KEY is not None and self._validate_license(self.LICENSE_KEY)

    def _validate_license(self, key: str) -> bool:
        # Cryptographic validation delegated to LicenseManager
        from core.licensing.license import LicenseManager
        try:
            LicenseManager.invalidate_cache()
            lic = LicenseManager.load(key)
            return lic.tier in ("enterprise", "starter")
        except Exception:
            return False


settings = Settings()  # type: ignore[call-arg]
