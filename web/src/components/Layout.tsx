import { BarChart3, ClipboardList, LogOut, Users, Warehouse, type LucideIcon } from "lucide-react";
import { NavLink, Navigate, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import type { Rol } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV: { to: string; label: string; icon: LucideIcon; roles: Rol[] }[] = [
  { to: "/usuarios", label: "Usuarios", icon: Users, roles: ["administrador"] },
  { to: "/inventario", label: "Inventario", icon: Warehouse, roles: ["administrador", "supervisor"] },
  { to: "/asignaciones", label: "Tomas y asignaciones", icon: ClipboardList, roles: ["administrador", "supervisor"] },
  { to: "/reportes", label: "Comparación y reportes", icon: BarChart3, roles: ["administrador", "supervisor"] },
];

export function Layout() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return <div className="grid min-h-screen place-items-center text-muted-foreground">Cargando…</div>;
  }
  if (!user) return <Navigate to="/login" replace />;

  const visibles = NAV.filter((n) => n.roles.includes(user.rol));

  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <aside className="flex flex-col border-r bg-card">
        <div className="flex items-center gap-3 border-b px-5 py-4">
          {/* Chip azul de marca para que el logo (blanco/amarillo) sea visible. */}
          <div className="rounded-md bg-primary px-2 py-1.5">
            <img src="/logo.png" alt="Colsubsidio" className="h-6 w-auto" />
          </div>
          <span className="font-semibold text-primary">Inventario</span>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {visibles.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive ? "bg-primary text-primary-foreground" : "hover:bg-accent",
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t p-3">
          <div className="mb-2 px-2 text-sm">
            <div className="font-medium">{user.nombre}</div>
            <div className="text-xs capitalize text-muted-foreground">{user.rol}</div>
          </div>
          <Button variant="outline" size="sm" className="w-full" onClick={logout}>
            <LogOut className="h-4 w-4" /> Salir
          </Button>
        </div>
      </aside>
      <main className="overflow-auto bg-background p-8">
        <Outlet />
      </main>
    </div>
  );
}
