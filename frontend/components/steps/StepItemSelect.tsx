"use client";
import { useState } from "react";
import { Package, ChevronDown, ChevronUp } from "lucide-react";
import { Order, OrderItem } from "@/lib/api";
import { RETURN_REASONS, ITEM_CONDITIONS } from "@/lib/constants";
import { Button } from "@/components/ui/Button";

export interface SelectedItem {
  order_item_id: string;
  quantity: number;
  reason: string;
  reason_detail?: string;
  condition?: string;
}

interface Props {
  order: Order;
  onNext: (items: SelectedItem[]) => void;
  onBack: () => void;
}

interface ItemState {
  selected: boolean;
  quantity: number;
  reason: string;
  reason_detail: string;
  condition: string;
  expanded: boolean;
}

export function StepItemSelect({ order, onNext, onBack }: Props) {
  const [items, setItems] = useState<Record<string, ItemState>>(() =>
    Object.fromEntries(
      order.items.map(item => [
        item.id,
        { selected: false, quantity: 1, reason: "", reason_detail: "", condition: "unopened", expanded: false },
      ])
    )
  );
  const [error, setError] = useState<string | null>(null);

  function update(id: string, patch: Partial<ItemState>) {
    setItems(prev => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  }

  function toggle(item: OrderItem) {
    const cur = items[item.id];
    update(item.id, { selected: !cur.selected, expanded: !cur.selected });
  }

  function handleNext() {
    const selected = order.items.filter(i => items[i.id].selected);
    if (selected.length === 0) {
      setError("Wybierz co najmniej jeden produkt.");
      return;
    }
    const missing = selected.find(i => !items[i.id].reason);
    if (missing) {
      setError(`Wybierz powód zwrotu dla: ${missing.name}`);
      return;
    }
    setError(null);
    onNext(
      selected.map(i => ({
        order_item_id: i.id,
        quantity: items[i.id].quantity,
        reason: items[i.id].reason,
        reason_detail: items[i.id].reason_detail || undefined,
        condition: items[i.id].condition || undefined,
      }))
    );
  }

  const selectedCount = Object.values(items).filter(i => i.selected).length;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">Wybierz produkty do zwrotu</h2>
        <p className="text-sm text-gray-500 mt-1">Zamówienie {order.order_number}</p>
      </div>

      <div className="flex flex-col gap-3">
        {order.items.map(item => {
          const state = items[item.id];
          return (
            <div
              key={item.id}
              className={`border rounded-2xl overflow-hidden transition-all ${state.selected ? "border-[var(--brand)] bg-[var(--brand-light)]" : "border-gray-200 bg-white"}`}
            >
              {/* Item header — tap to select */}
              <div
                className="flex items-center gap-3 p-4 cursor-pointer"
                onClick={() => toggle(item)}
              >
                {/* Checkbox */}
                <div className={`w-5 h-5 rounded-md border-2 shrink-0 flex items-center justify-center transition-colors
                  ${state.selected ? "bg-[var(--brand)] border-[var(--brand)]" : "border-gray-300"}`}>
                  {state.selected && <span className="text-white text-xs">✓</span>}
                </div>

                {/* Image */}
                <div className="w-12 h-12 rounded-xl bg-gray-100 shrink-0 overflow-hidden">
                  {item.image_url
                    ? <img src={item.image_url} alt={item.name} className="w-full h-full object-cover" />
                    : <Package size={24} className="m-auto mt-3 text-gray-300" />
                  }
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{item.name}</p>
                  {item.variant && <p className="text-xs text-gray-400">{item.variant}</p>}
                  <p className="text-sm font-semibold text-gray-700 mt-0.5">
                    {item.unit_price_gross.toFixed(2)} {order.currency}
                  </p>
                </div>

                {state.selected && (
                  <button onClick={e => { e.stopPropagation(); update(item.id, { expanded: !state.expanded }); }}
                    className="text-gray-400 shrink-0">
                    {state.expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </button>
                )}
              </div>

              {/* Expanded detail form */}
              {state.selected && state.expanded && (
                <div className="px-4 pb-4 flex flex-col gap-3 border-t border-[var(--brand)]/20 pt-3">
                  {/* Quantity */}
                  {item.quantity > 1 && (
                    <div>
                      <label className="text-xs font-medium text-gray-600 mb-1 block">Ilość do zwrotu</label>
                      <div className="flex items-center gap-3">
                        <button onClick={() => update(item.id, { quantity: Math.max(1, state.quantity - 1) })}
                          className="w-8 h-8 rounded-lg border border-gray-200 flex items-center justify-center text-gray-600">−</button>
                        <span className="text-sm font-medium w-6 text-center">{state.quantity}</span>
                        <button onClick={() => update(item.id, { quantity: Math.min(item.quantity, state.quantity + 1) })}
                          className="w-8 h-8 rounded-lg border border-gray-200 flex items-center justify-center text-gray-600">+</button>
                        <span className="text-xs text-gray-400">/ {item.quantity} szt.</span>
                      </div>
                    </div>
                  )}

                  {/* Reason */}
                  <div>
                    <label className="text-xs font-medium text-gray-600 mb-1 block">Powód zwrotu *</label>
                    <select
                      value={state.reason}
                      onChange={e => update(item.id, { reason: e.target.value })}
                      className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)] bg-white"
                    >
                      <option value="">Wybierz powód...</option>
                      {RETURN_REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                    </select>
                  </div>

                  {/* Condition */}
                  <div>
                    <label className="text-xs font-medium text-gray-600 mb-1 block">Stan produktu</label>
                    <div className="grid grid-cols-2 gap-2">
                      {ITEM_CONDITIONS.map(c => (
                        <button
                          key={c.value}
                          onClick={() => update(item.id, { condition: c.value })}
                          className={`text-xs px-3 py-2 rounded-xl border transition-colors text-left
                            ${state.condition === c.value ? "border-[var(--brand)] bg-[var(--brand)] text-white" : "border-gray-200 text-gray-600"}`}
                        >
                          {c.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Detail */}
                  <div>
                    <label className="text-xs font-medium text-gray-600 mb-1 block">Dodatkowy opis (opcjonalnie)</label>
                    <textarea
                      rows={2}
                      value={state.reason_detail}
                      onChange={e => update(item.id, { reason_detail: e.target.value })}
                      placeholder="Opisz problem..."
                      className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[var(--brand)]"
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">
          {error}
        </div>
      )}

      <div className="flex gap-3 mt-2">
        <Button variant="ghost" onClick={onBack} className="flex-1">← Wróć</Button>
        <Button onClick={handleNext} className="flex-1" disabled={selectedCount === 0}>
          Dalej ({selectedCount}) →
        </Button>
      </div>
    </div>
  );
}
