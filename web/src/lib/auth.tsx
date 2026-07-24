import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { endpoints, tokenStore, type Usuario } from "@/lib/api";

interface AuthState {
  user: Usuario | null;
  loading: boolean;
  login: (cedula: string, password: string) => Promise<Usuario>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Usuario | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Rehidrata la sesión si hay token guardado.
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    endpoints
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  async function login(cedula: string, password: string) {
    const res = await endpoints.loginWeb(cedula, password);
    tokenStore.set(res.access_token);
    const me = await endpoints.me();
    setUser(me);
    return me;
  }

  function logout() {
    tokenStore.clear();
    setUser(null);
  }

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
