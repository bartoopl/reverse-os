"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Pencil, Power, ChevronUp, ChevronDown } from "lucide-react";
import { adminApi, RuleSet } from "@/lib/admin-api";

const EMPTY_RULE: Partial<RuleSet> = {
  name: "",
  description: "",
  priority: 100,
  conditions: { all: [] },
  actions: [],
  platform: undefined,
};

const ACTION_TYPES = [
  "approve_instant",
  "require_inspection",
  "reject_return",
  "keep_it",
  "free_shipping_toggle",
  "offer_store_credit_bonus",
];

export default function AdminRules() {
  const router = useRouter();
  const [rules, setRules] = useState<RuleSet[]>([]);
  const [editing, setEditing] = useState<Partial<RuleSet> | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) { router.push("/admin/login"); return; }
    adminApi.rules.list().then(setRules);
  }, []);

  async function save() {
    if (!editing) return;
    setSaving(true);
    setError(null);
    try {
      if (editing.id) {
        const updated = await adminApi.rules.update(editing.id, editing);
        setRules(r => r.map(x => x.id === updated.id ? updated : x));
      } else {
        const created = await adminApi.rules.create(editing);
        setRules(r => [...r, created].sort((a, b) => a.priority - b.priority));
      }
      setEditing(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(rule: RuleSet) {
    if (rule.is_active) {
      await adminApi.rules.deactivate(rule.id);
      setRules(r => r.map(x => x.id === rule.id ? { ...x, is_active: false } : x));
    } else {
      const updated = await adminApi.rules.update(rule.id, { is_active: true });
      setRules(r => r.map(x => x.id === updated.id ? updated : x));
    }
  }

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Reguły</h1>
          <p className="text-gray-400 text-sm mt-0.5">Silnik decyzji zwrotów — reguły w kolejności priorytetu</p>
        </div>
        <button
          onClick={() => setEditing({ ...EMPTY_RULE })}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2.5 rounded-xl transition-colors"
        >
          <Plus size={15} />
          Nowa reguła
        </button>
      </div>

      <div className="flex flex-col gap-3">
        {rules.map(rule => (
          <div
            key={rule.id}
            className={`bg-gray-900 border rounded-2xl p-5 transition-opacity ${rule.is_active ? "border-gray-800" : "border-gray-800/50 opacity-50"}`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="text-xs font-mono bg-gray-800 text-gray-400 px-2 py-1 rounded-lg mt-0.5">
                  #{rule.priority}
                </span>
                <div>
                  <p className="text-white font-medium text-sm">{rule.name}</p>
                  {rule.description && <p className="text-xs text-gray-500 mt-0.5">{rule.description}</p>}
                  <div className="flex gap-2 mt-2 flex-wrap">
                    {rule.actions.map((a, i) => (
                      <span key={i} className="text-xs bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded-full">{a.type}</span>
                    ))}
                    {rule.platform && (
                      <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full">{rule.platform}</span>
                    )}
                    <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full">v{rule.version}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setEditing({ ...rule })}
                  className="p-2 text-gray-500 hover:text-white hover:bg-gray-800 rounded-xl transition-colors"
                >
                  <Pencil size={14} />
                </button>
                <button
                  onClick={() => toggleActive(rule)}
                  className={`p-2 rounded-xl transition-colors ${rule.is_active ? "text-green-400 hover:bg-gray-800" : "text-gray-600 hover:text-green-400 hover:bg-gray-800"}`}
                >
                  <Power size={14} />
                </button>
              </div>
            </div>

            {/* Conditions preview */}
            <div className="mt-3 pt-3 border-t border-gray-800">
              <p className="text-xs text-gray-600 font-mono">
                {JSON.stringify(rule.conditions).slice(0, 120)}
                {JSON.stringify(rule.conditions).length > 120 ? "…" : ""}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-white font-semibold mb-5">{editing.id ? "Edytuj regułę" : "Nowa reguła"}</h2>

            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="text-xs text-gray-400 mb-1 block">Nazwa *</label>
                  <input
                    value={editing.name ?? ""}
                    onChange={e => setEditing(d => ({ ...d!, name: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Priorytet (niższy = wyższy)</label>
                  <input
                    type="number"
                    value={editing.priority ?? 100}
                    onChange={e => setEditing(d => ({ ...d!, priority: +e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-xl px-3 py-2.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Platforma (opcjonalnie)</label>
                  <select
                    value={editing.platform ?? ""}
                    onChange={e => setEditing(d => ({ ...d!, platform: e.target.value || undefined }))}
                    className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-xl px-3 py-2.5 focus:outline-none"
                  >
                    <option value="">Wszystkie</option>
                    <option value="shopify">Shopify</option>
                    <option value="magento">Magento</option>
                    <option value="woocommerce">WooCommerce</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="text-xs text-gray-400 mb-1 block">Opis</label>
                  <input
                    value={editing.description ?? ""}
                    onChange={e => setEditing(d => ({ ...d!, description: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-xl px-3 py-2.5 focus:outline-none"
                  />
                </div>
              </div>

              {/* Actions */}
              <div>
                <label className="text-xs text-gray-400 mb-2 block">Akcje</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {(editing.actions ?? []).map((a, i) => (
                    <span key={i} className="flex items-center gap-1.5 text-xs bg-indigo-500/20 text-indigo-300 px-2 py-1 rounded-full">
                      {a.type}
                      <button onClick={() => setEditing(d => ({ ...d!, actions: d!.actions!.filter((_, j) => j !== i) }))}
                        className="text-indigo-400 hover:text-red-400">×</button>
                    </span>
                  ))}
                </div>
                <select
                  onChange={e => {
                    if (!e.target.value) return;
                    setEditing(d => ({ ...d!, actions: [...(d!.actions ?? []), { type: e.target.value }] }));
                    e.target.value = "";
                  }}
                  className="bg-gray-800 border border-gray-700 text-gray-400 text-sm rounded-xl px-3 py-2 focus:outline-none"
                  defaultValue=""
                >
                  <option value="">+ Dodaj akcję…</option>
                  {ACTION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>

              {/* Conditions JSON */}
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Warunki (JSON)</label>
                <textarea
                  rows={6}
                  value={JSON.stringify(editing.conditions, null, 2)}
                  onChange={e => {
                    try { setEditing(d => ({ ...d!, conditions: JSON.parse(e.target.value) })); }
                    catch {}
                  }}
                  className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-xs font-mono rounded-xl px-3 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <p className="text-xs text-gray-600 mt-1">
                  Fakty: item_price_max, total_order_value, customer_segment, days_since_purchase, return_reason, customer_return_rate
                </p>
              </div>

              {error && <p className="text-red-400 text-sm">{error}</p>}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setEditing(null)}
                  className="flex-1 text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 text-sm font-medium py-2.5 rounded-xl transition-colors"
                >
                  Anuluj
                </button>
                <button
                  onClick={save}
                  disabled={saving || !editing.name}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-medium py-2.5 rounded-xl transition-colors"
                >
                  {saving ? "Zapisuję..." : "Zapisz regułę"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
