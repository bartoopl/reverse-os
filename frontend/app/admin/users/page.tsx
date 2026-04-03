"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { UserPlus, KeyRound, PowerOff, Power, Shield } from "lucide-react";
import { adminApi, User } from "@/lib/admin-api";

const ROLES = ["admin", "warehouse", "viewer", "api_key"];
const ROLE_COLORS: Record<string, string> = {
  admin:     "bg-red-900 text-red-300",
  warehouse: "bg-yellow-900 text-yellow-300",
  viewer:    "bg-blue-900 text-blue-300",
  api_key:   "bg-purple-900 text-purple-300",
};

export default function AdminUsers() {
  const router = useRouter();
  const [users, setUsers]       = useState<User[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [resetTarget, setResetTarget] = useState<User | null>(null);
  const [newUser, setNewUser]   = useState({ email: "", name: "", role: "viewer", password: "" });
  const [newPw, setNewPw]       = useState("");
  const [saving, setSaving]     = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) { router.push("/admin/login"); return; }
    load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setUsers(await adminApi.users.list());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function createUser() {
    if (!newUser.email || !newUser.password) return;
    setSaving(true);
    try {
      await adminApi.users.create(newUser);
      setShowCreate(false);
      setNewUser({ email: "", name: "", role: "viewer", password: "" });
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(u: User) {
    try {
      await adminApi.users.update(u.id, { is_active: !u.is_active });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function changeRole(u: User, role: string) {
    try {
      await adminApi.users.update(u.id, { role });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function resetPassword() {
    if (!resetTarget || newPw.length < 8) return;
    setSaving(true);
    try {
      await adminApi.users.resetPassword(resetTarget.id, newPw);
      setResetTarget(null);
      setNewPw("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="text-indigo-400" size={24} />
          <h1 className="text-2xl font-bold text-white">Użytkownicy</h1>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          <UserPlus size={16} /> Nowy użytkownik
        </button>
      </div>

      {error && (
        <div className="mb-4 bg-red-900/50 border border-red-700 text-red-300 px-4 py-3 rounded-lg text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">OK</button>
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md">
            <h2 className="text-white font-semibold text-lg mb-4">Nowy użytkownik</h2>
            <div className="space-y-3">
              <input
                className="w-full bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-sm"
                placeholder="Email"
                type="email"
                value={newUser.email}
                onChange={e => setNewUser(p => ({ ...p, email: e.target.value }))}
              />
              <input
                className="w-full bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-sm"
                placeholder="Imię i nazwisko (opcjonalne)"
                value={newUser.name}
                onChange={e => setNewUser(p => ({ ...p, name: e.target.value }))}
              />
              <select
                className="w-full bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-sm"
                value={newUser.role}
                onChange={e => setNewUser(p => ({ ...p, role: e.target.value }))}
              >
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
              <input
                className="w-full bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-sm"
                placeholder="Hasło (min. 8 znaków)"
                type="password"
                value={newUser.password}
                onChange={e => setNewUser(p => ({ ...p, password: e.target.value }))}
              />
            </div>
            <div className="flex gap-3 mt-5">
              <button
                onClick={createUser}
                disabled={saving}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium"
              >
                {saving ? "Tworzenie..." : "Utwórz"}
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 py-2 rounded-lg text-sm"
              >
                Anuluj
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset password modal */}
      {resetTarget && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm">
            <h2 className="text-white font-semibold text-lg mb-1">Reset hasła</h2>
            <p className="text-gray-400 text-sm mb-4">{resetTarget.email}</p>
            <input
              className="w-full bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-sm mb-4"
              placeholder="Nowe hasło (min. 8 znaków)"
              type="password"
              value={newPw}
              onChange={e => setNewPw(e.target.value)}
            />
            <div className="flex gap-3">
              <button
                onClick={resetPassword}
                disabled={saving || newPw.length < 8}
                className="flex-1 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium"
              >
                {saving ? "..." : "Resetuj"}
              </button>
              <button
                onClick={() => { setResetTarget(null); setNewPw(""); }}
                className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 py-2 rounded-lg text-sm"
              >
                Anuluj
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Users table */}
      {loading ? (
        <div className="text-gray-400 py-12 text-center">Ładowanie...</div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
                <th className="text-left px-4 py-3">Użytkownik</th>
                <th className="text-left px-4 py-3">Rola</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Ostatnie logowanie</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-3">
                    <div className="text-white font-medium">{u.name ?? "—"}</div>
                    <div className="text-gray-400 text-xs">{u.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      onChange={e => changeRole(u, e.target.value)}
                      className={`text-xs font-medium px-2 py-1 rounded border-0 cursor-pointer ${ROLE_COLORS[u.role] ?? "bg-gray-700 text-gray-300"}`}
                    >
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${u.is_active ? "bg-green-900 text-green-300" : "bg-gray-700 text-gray-400"}`}>
                      {u.is_active ? "Aktywny" : "Nieaktywny"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString("pl-PL") : "Nigdy"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={() => setResetTarget(u)}
                        title="Reset hasła"
                        className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-amber-400"
                      >
                        <KeyRound size={14} />
                      </button>
                      <button
                        onClick={() => toggleActive(u)}
                        title={u.is_active ? "Dezaktywuj" : "Aktywuj"}
                        className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
                      >
                        {u.is_active ? <PowerOff size={14} /> : <Power size={14} />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-gray-500">
                    Brak użytkowników
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
