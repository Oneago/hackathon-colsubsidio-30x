import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [cedula, setCedula] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(cedula, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo iniciar sesión");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          {/* Fondo azul de marca: el logotipo (isotipo amarillo + texto blanco)
              no contrasta sobre blanco. Blanco/amarillo sobre azul cumple WCAG. */}
          <div className="mb-3 rounded-xl bg-primary px-6 py-4">
            <img src="/logo.png" alt="Colsubsidio" className="h-14 w-auto" />
          </div>
          <CardTitle>Consola de Inventario</CardTitle>
          <CardDescription>Hoteles Colsubsidio — administradores y supervisores</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="cedula">Cédula</Label>
              <Input id="cedula" value={cedula} onChange={(e) => setCedula(e.target.value)} autoFocus required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
            )}
            <Button type="submit" variant="accent" className="w-full" disabled={busy}>
              {busy ? "Ingresando…" : "Ingresar"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
