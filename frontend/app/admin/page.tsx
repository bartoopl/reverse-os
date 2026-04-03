"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, Package, Zap, Clock, ArrowRight } from "lucide-react";
import Link from "next/link";
import { adminApi, Stats } from "@/lib/admin-api";
import { STATUS_LABELS } from "@/lib/constants";

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; color: string;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</span>
        <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${color}`}>
          <Icon size={15} />
        </div>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

function StatusPill({ status, count }: { status: string; count: number }) {
  const { label, color } = STATUS_LABELS[status] ?? { label: status, color: "text-gray-400" };
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
      <span className={`text-sm font-medium ${color}`}>{label}</span>
      <span className="text-sm text-white font-semibold tabular-nums">{count}</span>
    </div>
  );
}

export default function AdminDashboard() {
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) { router.push("/admin/login"); return; }
    adminApi.stats()
      .then(setStats)
      .catch(e => setError(e.message));
  }, []);

  if (error) return (
    <div className="p-8 text-red-400">{error}</div>
  );
  if (!stats) return (
    <div className="p-8 text-gray-500 animate-pulse">Ładowanie danych...</div>
  );

  const topStatuses = Object.entries(stats.by_status)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8);

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-0.5">Przegląd systemu zwrotów</p>
        </div>
        <Link href="/admin/returns" className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300">
          Wszystkie zwroty <ArrowRight size={14} />
        </Link>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Łącznie zwrotów"       value={stats.total}       icon={Package}   color="bg-indigo-500/20 text-indigo-400" />
        <StatCard label="Dziś"                  value={stats.today}       icon={TrendingUp} color="bg-green-500/20 text-green-400" sub="nowych zgłoszeń" />
        <StatCard label="Auto-zatwierdzenia"    value={`${stats.auto_approval_rate_pct}%`} icon={Zap} color="bg-yellow-500/20 text-yellow-400" sub="reguły engine" />
        <StatCard label="Kolejka magazynu"      value={stats.warehouse_queue} icon={Clock} color="bg-orange-500/20 text-orange-400" sub="do inspekcji" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status breakdown */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Statusy zwrotów</h2>
          {topStatuses.map(([status, count]) => (
            <StatusPill key={status} status={status} count={count} />
          ))}
        </div>

        {/* Trend last 30 days */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-white mb-1">Trend (30 dni)</h2>
          <p className="text-xs text-gray-500 mb-4">Liczba nowych zwrotów dziennie</p>
          <div className="flex items-end gap-1 h-32">
            {stats.trend_30d.length === 0 ? (
              <p className="text-gray-600 text-sm">Brak danych</p>
            ) : (() => {
              const max = Math.max(...stats.trend_30d.map(d => d.count), 1);
              return stats.trend_30d.map(d => (
                <div key={d.date} className="flex-1 flex flex-col items-center gap-1" title={`${d.date}: ${d.count}`}>
                  <div
                    className="w-full bg-indigo-500 rounded-sm min-h-[2px] transition-all"
                    style={{ height: `${(d.count / max) * 100}%` }}
                  />
                </div>
              ));
            })()}
          </div>
          {stats.avg_refund_pln > 0 && (
            <p className="text-xs text-gray-500 mt-4">
              Średni zwrot: <span className="text-white font-medium">{stats.avg_refund_pln.toFixed(2)} PLN</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
