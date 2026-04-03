// All calls go through Next.js BFF routes — cookie handled server-side.
// /api/orders → app/api/orders/route.ts → backend (with X-Session-Id)
// /api/returns → app/api/returns/route.ts → backend (with X-Session-Id, consumes session)

export interface OrderItem {
  id: string;
  sku: string;
  name: string;
  variant: string | null;
  quantity: number;
  unit_price_gross: number;
  image_url: string | null;
}

export interface Order {
  external_id: string;
  platform: string;
  order_number: string;
  ordered_at: string;
  currency: string;
  total_gross: number;
  items: OrderItem[];
}

export interface ReturnItemPayload {
  order_item_id: string;
  quantity: number;
  reason: string;
  reason_detail?: string;
  condition?: string;
}

export interface InitiateReturnPayload {
  platform: string;
  external_order_id: string;
  items: ReturnItemPayload[];
  return_method: string;
  customer_notes?: string;
}

export interface ReturnResult {
  id: string;
  rma_number: string;
  status: string;
  return_method: string | null;
  rule_decision: string | null;
  label_url: string | null;
  tracking_number: string | null;
  approved_refund_amount: number | null;
  created_at: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

export const api = {
  // Calls BFF proxy — cookie sent automatically, no token in URL
  fetchOrder: (orderId: string, platform: string) =>
    request<Order>(`/api/orders?orderId=${encodeURIComponent(orderId)}&platform=${platform}`),

  // Calls BFF proxy — session consumed atomically on submission
  initiateReturn: (payload: InitiateReturnPayload) =>
    request<ReturnResult>("/api/returns", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getReturn: (rmaNumber: string) => {
    const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
    return request<ReturnResult>(`${API}/returns/${rmaNumber}`);
  },
};
