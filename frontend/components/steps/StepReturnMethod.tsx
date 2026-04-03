"use client";
import { useState } from "react";
import { RETURN_METHODS } from "@/lib/constants";
import { Button } from "@/components/ui/Button";

interface Props {
  onNext: (method: string, notes: string) => void;
  onBack: () => void;
}

export function StepReturnMethod({ onNext, onBack }: Props) {
  const [method, setMethod] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleNext() {
    if (!method) {
      setError("Wybierz metodę zwrotu.");
      return;
    }
    setError(null);
    onNext(method, notes);
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">Wybierz metodę zwrotu</h2>
        <p className="text-sm text-gray-500 mt-1">Jak chcesz odesłać paczkę?</p>
      </div>

      <div className="flex flex-col gap-3">
        {RETURN_METHODS.map(m => (
          <button
            key={m.value}
            onClick={() => setMethod(m.value)}
            className={`flex items-center gap-4 p-4 rounded-2xl border-2 text-left transition-all
              ${method === m.value
                ? "border-[var(--brand)] bg-[var(--brand-light)]"
                : "border-gray-200 bg-white hover:border-gray-300"}`}
          >
            <span className="text-3xl shrink-0">{m.icon}</span>
            <div className="flex-1">
              <p className={`font-medium text-sm ${method === m.value ? "text-[var(--brand)]" : "text-gray-900"}`}>
                {m.label}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">{m.description}</p>
            </div>
            <div className={`w-5 h-5 rounded-full border-2 shrink-0 flex items-center justify-center
              ${method === m.value ? "border-[var(--brand)] bg-[var(--brand)]" : "border-gray-300"}`}>
              {method === m.value && <div className="w-2 h-2 rounded-full bg-white" />}
            </div>
          </button>
        ))}
      </div>

      <div>
        <label className="text-sm font-medium text-gray-700 mb-1 block">
          Uwagi dla obsługi <span className="text-gray-400 font-normal">(opcjonalnie)</span>
        </label>
        <textarea
          rows={3}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Np. adres do odbioru, dodatkowe informacje..."
          className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[var(--brand)]"
        />
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <Button variant="ghost" onClick={onBack} className="flex-1">← Wróć</Button>
        <Button onClick={handleNext} className="flex-1" disabled={!method}>
          Wyślij zgłoszenie →
        </Button>
      </div>
    </div>
  );
}
