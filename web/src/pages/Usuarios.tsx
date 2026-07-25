import { KeyRound } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { ApiError, endpoints, type Bodega, type Rol, type Usuario } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const ROLES: Rol[] = ["administrador", "supervisor", "supernumerario"];

export function Usuarios() {
  const { user: yo } = useAuth();
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [msg, setMsg] = useState<{ tipo: "ok" | "err"; texto: string } | null>(null);

  const [nombre, setNombre] = useState("");
  const [cedula, setCedula] = useState("");
  const [password, setPassword] = useState("");
  const [rol, setRol] = useState<Rol>("supernumerario");
  const [bodegaIds, setBodegaIds] = useState<number[]>([]);

  // Restablecimiento de contraseña: el usuario objetivo abre el modal.
  const [objetivo, setObjetivo] = useState<Usuario | null>(null);
  const [nuevaPassword, setNuevaPassword] = useState("");
  const [errorReset, setErrorReset] = useState<string | null>(null);
  const [resetBusy, setResetBusy] = useState(false);
  const [avisoReset, setAvisoReset] = useState<string | null>(null);

  async function recargar() {
    setUsuarios(await endpoints.usuarios());
  }

  useEffect(() => {
    endpoints.bodegas().then(setBodegas).catch(() => {});
    recargar().catch(() => {});
  }, []);

  function toggleBodega(id: number) {
    setBodegaIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    try {
      await endpoints.crearUsuario({ nombre, cedula, password, rol, bodega_ids: bodegaIds });
      setMsg({ tipo: "ok", texto: `Usuario ${nombre} creado` });
      setNombre("");
      setCedula("");
      setPassword("");
      setBodegaIds([]);
      await recargar();
    } catch (err) {
      setMsg({ tipo: "err", texto: err instanceof ApiError ? err.message : "Error al crear" });
    }
  }

  function abrirReset(u: Usuario) {
    setObjetivo(u);
    setNuevaPassword("");
    setErrorReset(null);
    setAvisoReset(null);
  }

  async function restablecer(e: React.FormEvent) {
    e.preventDefault();
    if (!objetivo) return;
    setErrorReset(null);
    setResetBusy(true);
    try {
      await endpoints.restablecerPassword(objetivo.id, nuevaPassword);
      setAvisoReset(`Contraseña de ${objetivo.nombre} restablecida. Ya puede ingresar con ella.`);
      setObjetivo(null);
      await recargar();
    } catch (err) {
      setErrorReset(err instanceof ApiError ? err.message : "No se pudo restablecer");
    } finally {
      setResetBusy(false);
    }
  }

  const requiereBodegas = rol !== "administrador";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Usuarios</h1>

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Crear usuario</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={crear} className="space-y-3">
              <div className="space-y-1.5">
                <Label>Nombre</Label>
                <Input value={nombre} onChange={(e) => setNombre(e.target.value)} required />
              </div>
              <div className="space-y-1.5">
                <Label>Cédula (CC)</Label>
                <Input value={cedula} onChange={(e) => setCedula(e.target.value)} required />
              </div>
              <div className="space-y-1.5">
                <Label>Contraseña asignada</Label>
                <Input value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
              </div>
              <div className="space-y-1.5">
                <Label>Rol</Label>
                <Select value={rol} onChange={(e) => setRol(e.target.value as Rol)}>
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </Select>
              </div>

              {requiereBodegas && (
                <div className="space-y-1.5">
                  <Label>
                    Bodegas{" "}
                    <span className="text-xs font-normal text-muted-foreground">
                      {rol === "supernumerario" ? "(exactamente 1)" : "(1 o más)"}
                    </span>
                  </Label>
                  <div className="max-h-44 space-y-1 overflow-auto rounded-md border p-2">
                    {bodegas.map((b) => (
                      <label key={b.id} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={bodegaIds.includes(b.id)}
                          onChange={() => toggleBodega(b.id)}
                        />
                        {b.nombre}
                        {b.es_operativa && <Badge variant="outline">operativa</Badge>}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {msg && (
                <p
                  className={
                    msg.tipo === "ok"
                      ? "rounded-md bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700"
                      : "rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
                  }
                >
                  {msg.texto}
                </p>
              )}
              <Button type="submit" className="w-full">
                Crear usuario
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Usuarios ({usuarios.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {avisoReset && (
              <p className="rounded-md bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">{avisoReset}</p>
            )}
            <Table>
              <THead>
                <TR>
                  <TH>Nombre</TH>
                  <TH>Cédula</TH>
                  <TH>Rol</TH>
                  <TH>Bodegas</TH>
                  <TH>Estado</TH>
                  <TH className="text-right">Acciones</TH>
                </TR>
              </THead>
              <TBody>
                {usuarios.map((u) => (
                  <TR key={u.id}>
                    <TD className="font-medium">{u.nombre}</TD>
                    <TD>{u.cedula}</TD>
                    <TD className="capitalize">{u.rol}</TD>
                    <TD className="text-muted-foreground">
                      {u.rol === "administrador" ? "todas" : u.bodegas.map((b) => b.nombre).join(", ") || "—"}
                    </TD>
                    <TD>
                      <Badge variant={u.activo ? "success" : "secondary"}>
                        {u.activo ? "activo" : "inactivo"}
                      </Badge>
                    </TD>
                    <TD className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => abrirReset(u)}
                        disabled={u.id === yo?.id}
                        aria-label={`Restablecer la contraseña de ${u.nombre}`}
                        title={
                          u.id === yo?.id
                            ? "Para su propia contraseña use el cambio de contraseña"
                            : `Restablecer la contraseña de ${u.nombre}`
                        }
                      >
                        <KeyRound className="h-4 w-4" />
                        Restablecer
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Dialog
        open={objetivo !== null}
        onClose={() => setObjetivo(null)}
        title="Restablecer contraseña"
        description={
          objetivo
            ? `${objetivo.nombre} — CC ${objetivo.cedula}. Esta será su contraseña de ingreso.`
            : undefined
        }
      >
        <form onSubmit={restablecer} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="nueva-password">Contraseña nueva</Label>
            <Input
              id="nueva-password"
              value={nuevaPassword}
              onChange={(e) => setNuevaPassword(e.target.value)}
              autoFocus
              required
              minLength={6}
              placeholder="Mínimo 6 caracteres"
            />
          </div>
          {errorReset && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{errorReset}</p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setObjetivo(null)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={resetBusy}>
              {resetBusy ? "Restableciendo…" : "Restablecer"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
