"""
Internal license key generator.
Run: python -m core.licensing.keygen --cid acme-gmbh --tier ENT --max 500 --exp 2027-01-01

NEVER ship this in the product binary. Internal tool only.
"""
import base64
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime


def generate(
    customer_id: str,
    tier: str,            # ENT or STR
    max_returns: int,     # 0 = unlimited
    expires: str,         # ISO date YYYY-MM-DD
    features: list[str],
) -> str:
    master_secret = os.environ.get("REVERSEOS_LICENSE_MASTER", "dev-secret-change-in-prod")

    exp_ts = int(datetime.fromisoformat(expires).timestamp()) if expires else 0

    payload = json.dumps({
        "cid": customer_id,
        "max_ret": max_returns,
        "exp": exp_ts,
        "features": features,
    }, separators=(",", ":"))

    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    prefix = f"REVOS-{tier}-{payload_b64}"
    sig = hmac.new(master_secret.encode(), prefix.encode(), hashlib.sha256).hexdigest()[:16].upper()

    return f"{prefix}-{sig}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate REVERSE-OS license key")
    parser.add_argument("--cid",      required=True, help="Customer ID")
    parser.add_argument("--tier",     default="ENT", choices=["ENT", "STR"])
    parser.add_argument("--max",      type=int, default=0, help="Max returns/month (0=unlimited)")
    parser.add_argument("--exp",      default="2027-01-01", help="Expiry date YYYY-MM-DD")
    parser.add_argument("--features", nargs="*", default=["auto_refund", "ksef", "rbac", "multi_store"])
    args = parser.parse_args()

    key = generate(args.cid, args.tier, args.max, args.exp, args.features)
    print(f"\nLicense key for {args.cid} [{args.tier}]:")
    print(f"  {key}\n")
