"use client";

const STEPS = [
  "Zamówienie",
  "Produkty",
  "Metoda",
  "Potwierdzenie",
];

export function ProgressBar({ current }: { current: number }) {
  return (
    <div className="w-full mb-8">
      <div className="flex items-center justify-between">
        {STEPS.map((label, i) => {
          const step = i + 1;
          const done = step < current;
          const active = step === current;
          return (
            <div key={step} className="flex-1 flex flex-col items-center gap-1">
              <div className="flex items-center w-full">
                {i > 0 && (
                  <div className={`flex-1 h-0.5 ${done ? "bg-[var(--brand)]" : "bg-gray-200"}`} />
                )}
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 transition-colors
                    ${done ? "bg-[var(--brand)] text-white" : active ? "border-2 border-[var(--brand)] text-[var(--brand)]" : "border-2 border-gray-200 text-gray-400"}`}
                >
                  {done ? "✓" : step}
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`flex-1 h-0.5 ${done ? "bg-[var(--brand)]" : "bg-gray-200"}`} />
                )}
              </div>
              <span className={`text-xs ${active ? "text-[var(--brand)] font-medium" : "text-gray-400"}`}>
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
