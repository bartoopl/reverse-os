"use client";
import { useState } from "react";
import { ShoppingBag } from "lucide-react";
import { api, Order } from "@/lib/api";
import { Button } from "@/components/ui/Button";

interface Props {
  prefillOrderId?: string;
  prefillPlatform?: string;
  onSuccess: (order: Order) => void;
}

export function StepOrderVerify({ prefillOrderId, prefillPlatform, onSuccess }: Props) {
  const [orderId, setOrderId] = useState(prefillOrderId ?? "");
  const [platform, setPlatform] = useState(prefillPlatform ?? "shopify");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFetch() {
    if (!orderId) {
      setError("Podaj numer zamówienia.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const order = await api.fetchOrder(orderId, platform);
      onSuccess(order);
    } catch (e: any) {
      if (e.message?.includes("401") || e.message?.includes("session")) {
        setError("Brak aktywnej sesji. Użyj linka z e-maila lub skontaktuj się z obsługą.");
      } else if (e.message?.includes("403")) {
        setError("Brak dostępu. Link zwrotu jest nieprawidłowy lub wygasł.");
      } else {
        setError(e.message ?? "Nie znaleziono zamówienia.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="w-14 h-14 rounded-2xl bg-[var(--brand-light)] flex items-center justify-center">
          <ShoppingBag size={28} className="text-[var(--brand)]" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Zwrot zamówienia</h2>
          <p className="text-sm text-gray-500 mt-1">
            Użyj linka z e-maila potwierdzającego zamówienie, aby automatycznie załadować swoje produkty.
          </p>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-sm text-blue-700">
        🔒 Token weryfikacyjny jest przechowywany bezpiecznie — nie jest widoczny w adresie URL.
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <label className="text-sm font-medium text-gray-700 mb-1 block">Platforma</label>
          <select
            value={platform}
            onChange={e => setPlatform(e.target.value)}
            className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)] bg-white"
          >
            <option value="shopify">Shopify</option>
            <option value="magento">Magento</option>
            <option value="woocommerce">WooCommerce</option>
            <option value="prestashop">PrestaShop</option>
          </select>
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 mb-1 block">Numer zamówienia</label>
          <input
            type="text"
            placeholder="np. #1001"
            value={orderId}
            onChange={e => setOrderId(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleFetch()}
            className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)]"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">
            {error}
          </div>
        )}

        <Button onClick={handleFetch} loading={loading} className="w-full mt-2">
          Sprawdź zamówienie →
        </Button>
      </div>
    </div>
  );
}
