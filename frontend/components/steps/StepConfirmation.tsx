"use client";
import { CheckCircle, Clock, XCircle, Package, ExternalLink } from "lucide-react";
import { ReturnResult } from "@/lib/api";
import { STATUS_LABELS, RETURN_METHODS } from "@/lib/constants";
import { Button } from "@/components/ui/Button";

interface Props {
  result: ReturnResult;
  onNewReturn: () => void;
}

function DecisionBanner({ decision }: { decision: string | null }) {
  if (decision === "auto_approved" || decision === "keep_it") {
    return (
      <div className="flex items-center gap-3 bg-green-50 border border-green-100 rounded-2xl p-4">
        <CheckCircle size={28} className="text-green-500 shrink-0" />
        <div>
          <p className="font-semibold text-green-800 text-sm">
            {decision === "keep_it" ? "Zatrzymaj produkt — zwrot zatwierdzony!" : "Zwrot zatwierdzony automatycznie!"}
          </p>
          <p className="text-xs text-green-600 mt-0.5">
            {decision === "keep_it"
              ? "Nie musisz odsyłać produktu. Refundacja zostanie przetworzona wkrótce."
              : "Twoje zgłoszenie zostało przetworzone. Etykieta zostanie wysłana na e-mail."}
          </p>
        </div>
      </div>
    );
  }
  if (decision === "require_inspection") {
    return (
      <div className="flex items-center gap-3 bg-orange-50 border border-orange-100 rounded-2xl p-4">
        <Clock size={28} className="text-orange-500 shrink-0" />
        <div>
          <p className="font-semibold text-orange-800 text-sm">Zgłoszenie wymaga weryfikacji</p>
          <p className="text-xs text-orange-600 mt-0.5">Nasz zespół przejrzy zgłoszenie w ciągu 1 dnia roboczego.</p>
        </div>
      </div>
    );
  }
  if (decision === "rejected") {
    return (
      <div className="flex items-center gap-3 bg-red-50 border border-red-100 rounded-2xl p-4">
        <XCircle size={28} className="text-red-500 shrink-0" />
        <div>
          <p className="font-semibold text-red-800 text-sm">Zwrot odrzucony</p>
          <p className="text-xs text-red-600 mt-0.5">Skontaktuj się z obsługą, jeśli uważasz to za błąd.</p>
        </div>
      </div>
    );
  }
  return null;
}

export function StepConfirmation({ result, onNewReturn }: Props) {
  const status = STATUS_LABELS[result.status] ?? { label: result.status, color: "text-gray-600" };
  const method = RETURN_METHODS.find(m => m.value === result.return_method);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col items-center gap-2 text-center">
        <div className="w-16 h-16 rounded-2xl bg-[var(--brand-light)] flex items-center justify-center">
          <Package size={32} className="text-[var(--brand)]" />
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Zgłoszenie przyjęte</h2>
        <p className="text-sm text-gray-500">Zachowaj numer RMA do śledzenia statusu</p>
      </div>

      {/* RMA badge */}
      <div className="bg-gray-50 border border-gray-200 rounded-2xl p-4 text-center">
        <p className="text-xs text-gray-500 mb-1">Numer zgłoszenia (RMA)</p>
        <p className="text-2xl font-mono font-bold text-gray-900 tracking-wider">{result.rma_number}</p>
        <span className={`inline-block mt-2 text-xs font-medium px-3 py-1 rounded-full bg-white border ${status.color}`}>
          {status.label}
        </span>
      </div>

      {/* Decision banner */}
      <DecisionBanner decision={result.rule_decision} />

      {/* Details */}
      <div className="flex flex-col gap-2">
        {method && (
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <span className="text-sm text-gray-500">Metoda zwrotu</span>
            <span className="text-sm font-medium text-gray-900">{method.icon} {method.label}</span>
          </div>
        )}
        {result.approved_refund_amount && (
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <span className="text-sm text-gray-500">Kwota refundacji</span>
            <span className="text-sm font-semibold text-green-700">{result.approved_refund_amount.toFixed(2)} PLN</span>
          </div>
        )}
        {result.tracking_number && (
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <span className="text-sm text-gray-500">Numer śledzenia</span>
            <span className="text-sm font-mono text-gray-900">{result.tracking_number}</span>
          </div>
        )}
        {result.label_url && (
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <span className="text-sm text-gray-500">Etykieta</span>
            <a
              href={result.label_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-sm text-[var(--brand)] font-medium"
            >
              Pobierz PDF <ExternalLink size={14} />
            </a>
          </div>
        )}
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded-2xl p-4 text-sm text-blue-700">
        Potwierdzenie zostanie wysłane na Twój e-mail. Status możesz sprawdzić wpisując numer RMA na naszej stronie.
      </div>

      <Button variant="outline" onClick={onNewReturn} className="w-full">
        Zgłoś kolejny zwrot
      </Button>
    </div>
  );
}
