"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { adminApi, ReturnListItem } from "@/lib/admin-api";
import { STATUS_LABELS } from "@/lib/constants";

const STATUS_OPTIONS = ["", "pending", "requires_inspection", "approved", "received", "refunded", "rejected", "closed"];

function StatusBadge({ status }: { status: string }) {
  const { label, color } = STATUS_LABELS[status] ?? { label: status, color: "text-gray-400" };
  return <span className={`text-xs font-medium ${color}`}>{label}</span>;
}

export default function AdminReturns() {
  const router = useRouter();
  const [items, setItems]   = useState<ReturnListItem[]>([]);
  const [total, setTotal]   = useState(0);
  const [page, setPage]     = useState(1);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) { router.push("/admin/login"); return; }
    setLoading(true);
    adminApi.returns.list(page, filter || undefined)
      .then(r => { setItems(r.items); setTotal(r.total); })
      .finally(() => setLoading(false));
  }, [page, filter]);

  const totalPages = Math.ceil(total / 25);

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Zwroty</h1>
          <p className="text-gray-400 text-sm mt-0.5">{total} zgłoszeń łącznie</p>
        </div>
        <select
          value={filter}
          onChange={e => { setFilter(e.target.value); setPage(1); }}
          className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {STATUS_OPTIONS.map(s => (
            <option key={s} value={s}>{s ? (STATUS_LABELS[s]?.label ?? s) : "Wszystkie statusy"}</option>
          ))}
        </select>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              {["RMA", "Status", "Platforma", "Decyzja", "Metoda", "Kwota", "Data"].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs text-gray-400 font-medium uppercase tracking-wide">{h}</th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-b border-gray-800">
                  {Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><div className="h-3 bg-gray-800 rounded animate-pulse w-20" /></td>
                  ))}
                </tr>
              ))
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-gray-500">Brak zwrotów</td>
              </tr>
            ) : items.map(ret => (
              <tr key={ret.id} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                <td className="px-4 py-3 font-mono text-indigo-400 text-xs">{ret.rma_number}</td>
                <td className="px-4 py-3"><StatusBadge status={ret.status} /></td>
                <td className="px-4 py-3 text-gray-400">{ret.platform ?? "—"}</td>
                <td className="px-4 py-3 text-gray-400">{ret.rule_decision ?? "—"}</td>
                <td className="px-4 py-3 text-gray-400">{ret.return_method ?? "—"}</td>
                <td className="px-4 py-3 text-gray-300">
                  {ret.approved_refund_amount ? `${ret.approved_refund_amount.toFixed(2)} PLN` : "—"}
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {ret.created_at ? new Date(ret.created_at).toLocaleDateString("pl-PL") : "—"}
                </td>
                <td className="px-4 py-3">
                  <Link href={`/admin/returns/${ret.id}`} className="text-gray-500 hover:text-indigo-400 transition-colors">
                    <ExternalLink size={14} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <span className="text-xs text-gray-500">Strona {page} z {totalPages}</span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
