/**
 * BFF proxy: return submission.
 * Reads `rsid` cookie → passes as X-Session-Id to backend.
 * Backend atomically consumes session + token on submit.
 */
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get("rsid")?.value;

  if (!sessionId) {
    return NextResponse.json({ detail: "No active session" }, { status: 401 });
  }

  const body = await request.json();

  const res = await fetch(`${API}/returns/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": sessionId,
    },
    body: JSON.stringify(body),
  });

  const data = await res.json();

  // On success, clear the session cookie — return was submitted
  const response = NextResponse.json(data, { status: res.status });
  if (res.ok) {
    response.cookies.set("rsid", "", { maxAge: 0, path: "/" });
  }
  return response;
}
