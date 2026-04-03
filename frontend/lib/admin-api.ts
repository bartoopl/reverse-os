const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("admin_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("admin_token");
    window.location.href = "/admin/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

export interface Stats {
  total: number;
  today: number;
  by_status: Record<string, number>;
  trend_30d: { date: string; count: number }[];
  avg_refund_pln: number;
  auto_approval_rate_pct: number;
  warehouse_queue: number;
}

export interface ReturnListItem {
  id: string;
  rma_number: string;
  status: string;
  platform: string | null;
  rule_decision: string | null;
  return_method: string | null;
  approved_refund_amount: number | null;
  created_at: string;
  submitted_at: string | null;
}

export interface ReturnDetail extends ReturnListItem {
  rule_log: any;
  requested_refund_amount: number | null;
  label_url: string | null;
  tracking_number: string | null;
  logistics_provider: string | null;
  ksef_reference: string | null;
  customer_notes: string | null;
  internal_notes: string | null;
  resolved_at: string | null;
  allowed_transitions: string[];
  items: any[];
  rule_log_entries: any[];
  audit_trail: any[];
}

export interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
}

export interface RuleSet {
  id: string;
  name: string;
  description: string | null;
  priority: number;
  is_active: boolean;
  platform: string | null;
  conditions: any;
  actions: any[];
  version: number;
  created_at: string;
}

export const adminApi = {
  login: async (email: string, password: string) => {
    const res = await fetch(`${API}/admin/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error("Nieprawidłowe dane logowania");
    return res.json() as Promise<{ access_token: string; role: string; name: string }>;
  },

  stats: () => request<Stats>("/admin/stats/"),

  returns: {
    list: (page = 1, status?: string) =>
      request<{ items: ReturnListItem[]; total: number; page: number; page_size: number }>(
        `/admin/returns/?page=${page}${status ? `&status=${status}` : ""}`
      ),
    get: (id: string) => request<ReturnDetail>(`/admin/returns/${id}`),
    overrideStatus: (id: string, newStatus: string, reason: string) =>
      request(`/admin/returns/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ new_status: newStatus, reason }),
      }),
    updateNotes: (id: string, notes: string) =>
      request(`/admin/returns/${id}/notes`, {
        method: "PATCH",
        body: JSON.stringify({ internal_notes: notes }),
      }),
  },

  financial: {
    refund: (returnId: string, provider: string, paymentId: string, amount: number) =>
      request(`/admin/financial/${returnId}/refund`, {
        method: "POST",
        body: JSON.stringify({ provider, original_payment_id: paymentId, amount }),
      }),
    storeCredit: (returnId: string, amount: number) =>
      request<{ code: string; amount: number; expires_at: string }>(
        `/admin/financial/${returnId}/store-credit`,
        { method: "POST", body: JSON.stringify({ amount }) }
      ),
    syncOrder: (returnId: string) =>
      request(`/admin/financial/${returnId}/sync-order`, { method: "POST" }),
  },

  users: {
    list: () => request<User[]>("/admin/users/"),
    create: (data: { email: string; name?: string; role: string; password: string }) =>
      request<User>("/admin/users/", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: { role?: string; is_active?: boolean; name?: string }) =>
      request<User>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    resetPassword: (id: string, password: string) =>
      request(`/admin/users/${id}/reset-password`, {
        method: "POST",
        body: JSON.stringify({ password }),
      }),
  },

  rules: {
    list: () => request<RuleSet[]>("/admin/rules/"),
    create: (data: Partial<RuleSet>) =>
      request<RuleSet>("/admin/rules/", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: Partial<RuleSet>) =>
      request<RuleSet>(`/admin/rules/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    deactivate: (id: string) =>
      request(`/admin/rules/${id}`, { method: "DELETE" }),
  },
};
