/**
 * Token redemption Route Handler.
 *
 * Entry point for email deep links:
 *   http://localhost:3000/redeem?orderId=X&platform=shopify&token=T
 *
 * What happens here (server-side, invisible to browser):
 *   1. Extract orderId, platform, token from query params
 *   2. POST to backend /auth/redeem — validates token, creates Redis session
 *   3. Set HttpOnly cookie `rsid` with the session ID
 *   4. Redirect to /return?orderId=X&platform=shopify  ← NO token in URL
 *
 * The raw token is never stored in browser history or visible after this redirect.
 */
import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const orderId   = searchParams.get("orderId");
  const platform  = searchParams.get("platform") ?? "shopify";
  const token     = searchParams.get("token");

  if (!orderId || !token) {
    return NextResponse.redirect(new URL("/return", origin));
  }

  try {
    const res = await fetch(`${API}/auth/redeem`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_id: orderId, platform, token }),
    });

    if (!res.ok) {
      // Token invalid/expired — send to portal, will show error on step 1
      return NextResponse.redirect(new URL("/return?error=invalid_token", origin));
    }

    const { session_id } = await res.json();

    // Redirect to clean URL — no token visible
    const destination = new URL(`/return?orderId=${encodeURIComponent(orderId)}&platform=${platform}`, origin);
    const response = NextResponse.redirect(destination);

    response.cookies.set("rsid", session_id, {
      httpOnly: true,
      sameSite: "strict",
      path: "/",
      maxAge: 3600, // matches Redis session TTL
      // secure: true  ← uncomment in production (requires HTTPS)
    });

    return response;
  } catch {
    return NextResponse.redirect(new URL("/return?error=server_error", origin));
  }
}
