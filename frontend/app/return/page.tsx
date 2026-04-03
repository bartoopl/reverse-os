"use client";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StepOrderVerify } from "@/components/steps/StepOrderVerify";
import { StepItemSelect, SelectedItem } from "@/components/steps/StepItemSelect";
import { StepReturnMethod } from "@/components/steps/StepReturnMethod";
import { StepConfirmation } from "@/components/steps/StepConfirmation";
import { api, Order, ReturnResult } from "@/lib/api";

type Step = 1 | 2 | 3 | 4;

function ReturnFlow() {
  const params = useSearchParams();
  const [step, setStep] = useState<Step>(1);
  const [order, setOrder] = useState<Order | null>(null);
  const [selectedItems, setSelectedItems] = useState<SelectedItem[]>([]);
  const [result, setResult] = useState<ReturnResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [autoLoading, setAutoLoading] = useState(false);
  const [autoError, setAutoError] = useState<string | null>(null);

  // After /redeem sets the cookie and redirects here with ?orderId=X&platform=Y
  // (no token — it's in the HttpOnly cookie via session)
  const prefillOrderId = params.get("orderId") ?? undefined;
  const prefillPlatform = params.get("platform") ?? undefined;
  const urlError = params.get("error");

  // Auto-fetch order if we arrived from a deep link (cookie already set by /redeem)
  useEffect(() => {
    if (!prefillOrderId || !prefillPlatform) return;
    setAutoLoading(true);
    api.fetchOrder(prefillOrderId, prefillPlatform)
      .then(fetchedOrder => {
        setOrder(fetchedOrder);
        setStep(2);
      })
      .catch(e => {
        setAutoError(e.message ?? "Nie udało się załadować zamówienia. Sesja mogła wygasnąć.");
      })
      .finally(() => setAutoLoading(false));
  }, [prefillOrderId, prefillPlatform]);

  function reset() {
    setStep(1);
    setOrder(null);
    setSelectedItems([]);
    setResult(null);
    setSubmitError(null);
    setAutoError(null);
  }

  async function handleMethodAndSubmit(method: string, notes: string) {
    if (!order || selectedItems.length === 0) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await api.initiateReturn({
        platform: order.platform,
        external_order_id: order.external_id,
        items: selectedItems,
        return_method: method,
        customer_notes: notes || undefined,
      });
      setResult(res);
      setStep(4);
    } catch (e: any) {
      setSubmitError(e.message ?? "Błąd podczas składania zgłoszenia.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--background)] flex flex-col items-center py-8 px-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-lg bg-[var(--brand)] flex items-center justify-center text-white font-bold text-sm">R</div>
          <span className="font-semibold text-gray-900">Zwroty</span>
        </div>

        <div className="bg-[var(--card)] rounded-3xl shadow-sm border border-gray-100 p-6">
          <ProgressBar current={step} />

          {/* Deep-link token errors from /redeem */}
          {(urlError || autoError) && step === 1 && (
            <div className="mb-4 bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">
              {urlError === "invalid_token" && "Link zwrotu jest nieprawidłowy lub wygasł. Poproś o nowy."}
              {urlError === "server_error" && "Wystąpił błąd serwera. Spróbuj ponownie."}
              {autoError}
            </div>
          )}

          {/* Loading state while auto-fetching from deep link */}
          {autoLoading && (
            <div className="flex items-center justify-center py-12 text-gray-400 text-sm gap-2">
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              Ładowanie zamówienia...
            </div>
          )}

          {!autoLoading && step === 1 && (
            <StepOrderVerify
              prefillOrderId={prefillOrderId}
              prefillPlatform={prefillPlatform}
              onSuccess={(fetchedOrder) => {
                setOrder(fetchedOrder);
                setStep(2);
              }}
            />
          )}

          {step === 2 && order && (
            <StepItemSelect
              order={order}
              onNext={(items) => { setSelectedItems(items); setStep(3); }}
              onBack={() => setStep(1)}
            />
          )}

          {step === 3 && (
            <>
              {submitError && (
                <div className="mb-4 bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">
                  {submitError}
                </div>
              )}
              <StepReturnMethod
                onNext={handleMethodAndSubmit}
                onBack={() => setStep(2)}
              />
            </>
          )}

          {step === 4 && result && (
            <StepConfirmation result={result} onNewReturn={reset} />
          )}
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          Powered by <span className="font-medium">REVERSE-OS</span>
        </p>
      </div>
    </div>
  );
}

export default function ReturnPage() {
  return (
    <Suspense>
      <ReturnFlow />
    </Suspense>
  );
}
