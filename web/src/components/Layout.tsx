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

  const marca = (
    <div className="flex items-center gap-3">
      {/* Chip azul de marca para que el logo (blanco/amarillo) sea visible. */}
      <div className="rounded-md bg-primary px-2 py-1.5">
        <img src="/logo.png" alt="Colsubsidio" className="h-6 w-auto" />
      </div>
      <span className="font-semibold text-primary">Inventario</span>
    </div>
  );

  const enlaces = visibles.map(({ to, label, icon: Icon }) => (
    <NavLink
      key={to}
      to={to}
      className={({ isActive }) =>
        cn(
          "flex shrink-0 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive ? "bg-primary text-primary-foreground" : "hover:bg-accent",
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </NavLink>
  ));

  return (
    // h-dvh + overflow oculto: la altura la fija la pantalla, no el contenido,
    // así el bloque de sesión queda siempre al pie del aside visible.
    <div className="flex h-dvh flex-col overflow-hidden md:grid md:grid-cols-[240px_1fr]">
      {/* Móvil: barra superior con la navegación en scroll horizontal. */}
      <header className="flex flex-col gap-2 border-b bg-card px-4 py-3 md:hidden">
        <div className="flex items-center justify-between gap-3">
          {marca}
          <Button variant="outline" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4" /> Salir
          </Button>
        </div>
        <nav className="-mx-1 flex gap-1 overflow-x-auto px-1">{enlaces}</nav>
      </header>

      {/* Escritorio: aside fijo con nav desplazable. */}
      <aside className="hidden min-h-0 flex-col border-r bg-card md:flex">
        <div className="border-b px-5 py-4">{marca}</div>
        <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-3">{enlaces}</nav>
        <div className="border-t p-3">
          <div className="mb-2 px-2 text-sm">
            <div className="truncate font-medium">{user.nombre}</div>
            <div className="text-xs capitalize text-muted-foreground">{user.rol}</div>
          </div>
          <Button variant="outline" size="sm" className="w-full" onClick={logout}>
            <LogOut className="h-4 w-4" /> Salir
          </Button>
        </div>
      </aside>

      <main className="min-h-0 flex-1 overflow-auto bg-background p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}
