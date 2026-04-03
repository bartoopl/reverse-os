"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, ExternalLink, Save, CreditCard, Gift, RefreshCw } from "lucide-react";
import { adminApi, ReturnDetail } from "@/lib/admin-api";
import { STATUS_LABELS, RETURN_REASONS } from "@/lib/constants";

function Badge({ status }: { status: string }) {
  const { label, color } = STATUS_LABELS[status] ?? { label: status, color: "text-gray-400" };
  return <span className={`font-medium ${color}`}>{label}</span>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-2 border-b border-gray-800 last:border-0 gap-4">
      <span className="text-xs text-gray-500 shrink-0">{label}</span>
      <span className="text-sm text-gray-200 text-right">{value ?? "—"}</span>
    </div>
  );
}

export default function ReturnDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [ret, setRet] = useState<ReturnDetail | null>(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [overrideStatus, setOverrideStatus] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [overriding, setOverriding] = useState(false);
  // Financial
  const [refundProvider, setRefundProvider] = useState("stripe");
  const [refundPaymentId, setRefundPaymentId] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [creditAmount, setCreditAmount] = useState("");
  const [financialMsg, setFinancialMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [financialLoading, setFinancialLoading] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) { router.push("/admin/login"); return; }
    adminApi.returns.get(id).then(r => { setRet(r); setNotes(r.internal_notes ?? ""); });
  }, [id]);

  async function saveNotes() {
    if (!ret) return;
    setSaving(true);
    await adminApi.returns.updateNotes(id, notes).finally(() => setSaving(false));
  }

  async function doRefund() {
    setFinancialLoading(true); setFinancialMsg(null);
    try {
      await adminApi.financial.refund(id, refundProvider, refundPaymentId, parseFloat(refundAmount));
      setFinancialMsg({ type: "ok", text: "Refund zlecony — Celery przetworzy go w tle." });
      const updated = await adminApi.returns.get(id); setRet(updated);
    } catch (e: any) { setFinancialMsg({ type: "err", text: e.message }); }
    finally { setFinancialLoading(false); }
  }

  async function doStoreCredit() {
    setFinancialLoading(true); setFinancialMsg(null);
    try {
      const v = await adminApi.financial.storeCredit(id, parseFloat(creditAmount));
      setFinancialMsg({ type: "ok", text: `Voucher wygenerowany: ${v.code}` });
      const updated = await adminApi.returns.get(id); setRet(updated);
    } catch (e: any) { setFinancialMsg({ type: "err", text: e.message }); }
    finally { setFinancialLoading(false); }
  }

  async function doSyncOrder() {
    setFinancialLoading(true); setFinancialMsg(null);
    try {
      await adminApi.financial.syncOrder(id);
      setFinancialMsg({ type: "ok", text: "Status zamówienia zsynchronizowany z platformą." });
    } catch (e: any) { setFinancialMsg({ type: "err", text: e.message }); }
    finally { setFinancialLoading(false); }
  }

  async function doOverride() {
    if (!overrideStatus || !overrideReason) return;
    setOverriding(true);
    try {
      await adminApi.returns.overrideStatus(id, overrideStatus, overrideReason);
      const updated = await adminApi.returns.get(id);
      setRet(updated);
      setOverrideStatus("");
      setOverrideReason("");
    } finally {
      setOverriding(false);
    }
  }

  if (!ret) return <div className="p-8 text-gray-500 animate-pulse">Ładowanie...</div>;

  return (
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link href="/admin/returns" className="text-gray-500 hover:text-white transition-colors">
          <ChevronLeft size={20} />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-white font-mono">{ret.rma_number}</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <Badge status={ret.status} />
            {ret.platform && <span className="text-xs text-gray-500">· {ret.platform}</span>}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left column */}
        <div className="lg:col-span-2 flex flex-col gap-5">
          {/* Return items */}
          <Section title="Produkty do zwrotu">
            {ret.items.length === 0 ? (
              <p className="text-gray-500 text-sm">Brak produktów</p>
            ) : ret.items.map((item, i) => {
              const reason = RETURN_REASONS.find(r => r.value === item.reason)?.label ?? item.reason;
              return (
                <div key={i} className="flex items-start justify-between py-2 border-b border-gray-800 last:border-0 gap-4">
                  <div>
                    <p className="text-sm text-gray-200">ID: <span className="font-mono text-xs">{item.order_item_id.slice(0, 8)}…</span></p>
                    <p className="text-xs text-gray-500 mt-0.5">{reason} · {item.quantity_requested} szt.</p>
                    {item.reason_detail && <p className="text-xs text-gray-600 mt-0.5 italic">"{item.reason_detail}"</p>}
                  </div>
                  <div className="text-right shrink-0">
                    {item.warehouse_decision && (
                      <span className={`text-xs font-medium ${item.warehouse_decision === "accept" ? "text-green-400" : "text-red-400"}`}>
                        {item.warehouse_decision}
                      </span>
                    )}
                    {item.refund_amount && <p className="text-sm text-white font-semibold">{item.refund_amount.toFixed(2)} PLN</p>}
                  </div>
                </div>
              );
            })}
          </Section>

          {/* Rule engine trace */}
          {ret.rule_log_entries.length > 0 && (
            <Section title="Ślad silnika reguł">
              {ret.rule_log_entries.map((entry, i) => (
                <div key={i} className={`flex items-center justify-between py-2 border-b border-gray-800 last:border-0`}>
                  <span className="text-sm text-gray-300">{entry.rule_name}</span>
                  <div className="flex items-center gap-2">
                    {entry.matched && entry.actions_taken?.map((a: any, j: number) => (
                      <span key={j} className="text-xs bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded-full">{a.type}</span>
                    ))}
                    <span className={`text-xs font-medium ${entry.matched ? "text-green-400" : "text-gray-600"}`}>
                      {entry.matched ? "✓ match" : "miss"}
                    </span>
                  </div>
                </div>
              ))}
            </Section>
          )}

          {/* Audit trail */}
          {ret.audit_trail.length > 0 && (
            <Section title="Historia zmian">
              {ret.audit_trail.map((a, i) => (
                <div key={i} className="py-2 border-b border-gray-800 last:border-0">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-300 font-medium">{a.action}</span>
                    <span className="text-xs text-gray-600">{a.created_at ? new Date(a.created_at).toLocaleString("pl-PL") : ""}</span>
                  </div>
                  {a.new_value && <p className="text-xs text-gray-500 mt-0.5">{JSON.stringify(a.new_value)}</p>}
                </div>
              ))}
            </Section>
          )}
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-5">
          {/* Details */}
          <Section title="Szczegóły">
            <Row label="Metoda" value={ret.return_method} />
            <Row label="Decyzja" value={ret.rule_decision} />
            <Row label="Kwota zatw." value={ret.approved_refund_amount ? `${ret.approved_refund_amount.toFixed(2)} PLN` : null} />
            <Row label="Dostawca" value={ret.logistics_provider} />
            <Row label="Tracking" value={ret.tracking_number} />
            {ret.label_url && (
              <Row label="Etykieta" value={
                <a href={ret.label_url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-indigo-400 text-xs">
                  PDF <ExternalLink size={10} />
                </a>
              } />
            )}
            <Row label="KSeF ref." value={ret.ksef_reference} />
            <Row label="Zgłoszono" value={ret.submitted_at ? new Date(ret.submitted_at).toLocaleDateString("pl-PL") : null} />
            <Row label="Zamknięto" value={ret.resolved_at ? new Date(ret.resolved_at).toLocaleDateString("pl-PL") : null} />
          </Section>

          {/* Manual status override */}
          {ret.allowed_transitions.length > 0 && (
            <Section title="Zmień status">
              <select
                value={overrideStatus}
                onChange={e => setOverrideStatus(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-xl px-3 py-2 mb-2 focus:outline-none"
              >
                <option value="">Wybierz nowy status…</option>
                {ret.allowed_transitions.map(s => (
                  <option key={s} value={s}>{STATUS_LABELS[s]?.label ?? s}</option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Powód zmiany (wymagany)"
                value={overrideReason}
                onChange={e => setOverrideReason(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-xl px-3 py-2 mb-3 focus:outline-none"
              />
              <button
                onClick={doOverride}
                disabled={!overrideStatus || !overrideReason || overriding}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-medium py-2 rounded-xl transition-colors"
              >
                {overriding ? "Zmieniam..." : "Zmień status"}
              </button>
            </Section>
          )}

          {/* Financial actions */}
          {["received", "partial_received", "keep_it", "approved"].includes(ret.status) && (
            <Section title="Akcje finansowe">
              {financialMsg && (
                <div className={`text-xs px-3 py-2 rounded-xl mb-3 ${financialMsg.type === "ok" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
                  {financialMsg.text}
                </div>
              )}

              {/* Refund */}
              <div className="mb-4 pb-4 border-b border-gray-800">
                <p className="text-xs text-gray-400 font-medium mb-2 flex items-center gap-1.5"><CreditCard size={12} /> Refund gotówkowy</p>
                <div className="flex flex-col gap-2">
                  <select value={refundProvider} onChange={e => setRefundProvider(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 focus:outline-none">
                    <option value="stripe">Stripe</option>
                    <option value="payu">PayU</option>
                  </select>
                  <input placeholder="Payment ID (np. pi_xxx)" value={refundPaymentId}
                    onChange={e => setRefundPaymentId(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 focus:outline-none" />
                  <input type="number" placeholder={`Kwota PLN (maks. ${ret.requested_refund_amount ?? "?"})`}
                    value={refundAmount} onChange={e => setRefundAmount(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 focus:outline-none" />
                  <button onClick={doRefund} disabled={financialLoading || !refundPaymentId || !refundAmount}
                    className="w-full bg-green-700 hover:bg-green-600 disabled:opacity-40 text-white text-xs font-medium py-2 rounded-lg transition-colors">
                    {financialLoading ? "..." : "Inicjuj refund"}
                  </button>
                </div>
              </div>

              {/* Store credit */}
              <div className="mb-4 pb-4 border-b border-gray-800">
                <p className="text-xs text-gray-400 font-medium mb-2 flex items-center gap-1.5"><Gift size={12} /> Store credit (voucher)</p>
                <div className="flex gap-2">
                  <input type="number" placeholder="Kwota PLN" value={creditAmount}
                    onChange={e => setCreditAmount(e.target.value)}
                    className="flex-1 bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 focus:outline-none" />
                  <button onClick={doStoreCredit} disabled={financialLoading || !creditAmount}
                    className="bg-indigo-700 hover:bg-indigo-600 disabled:opacity-40 text-white text-xs font-medium px-3 py-2 rounded-lg transition-colors">
                    {financialLoading ? "..." : "Generuj"}
                  </button>
                </div>
              </div>

              {/* Sync */}
              <button onClick={doSyncOrder} disabled={financialLoading}
                className="flex items-center gap-2 text-xs text-gray-400 hover:text-white transition-colors disabled:opacity-40">
                <RefreshCw size={12} /> Synchronizuj status z platformą
              </button>
            </Section>
          )}

          {/* Internal notes */}
          <Section title="Notatki wewnętrzne">
            <textarea
              rows={4}
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Notatki widoczne tylko dla administratorów..."
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-xl px-3 py-2 resize-none focus:outline-none mb-2"
            />
            <button
              onClick={saveNotes}
              disabled={saving}
              className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300 disabled:opacity-40 transition-colors"
            >
              <Save size={14} />
              {saving ? "Zapisuję..." : "Zapisz notatki"}
            </button>
          </Section>
        </div>
      </div>
    </div>
  );
}
