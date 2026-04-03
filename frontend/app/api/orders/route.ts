/**
 * BFF proxy: order fetch.
 * Reads `rsid` HttpOnly cookie → passes as X-Session-Id to backend.
 * Token never leaves the backend/Redis.
 */
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export async function GET(request: NextRequest) {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get("rsid")?.value;

  if (!sessionId) {
    return NextResponse.json({ detail: "No active session" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const orderId  = searchParams.get("orderId");
  const platform = searchParams.get("platform");

  if (!orderId || !platform) {
    return NextResponse.json({ detail: "Missing orderId or platform" }, { status: 400 });
  }

  const res = await fetch(
    `${API}/orders/${encodeURIComponent(orderId)}?platform=${platform}`,
    { headers: { "X-Session-Id": sessionId } },
  );

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
