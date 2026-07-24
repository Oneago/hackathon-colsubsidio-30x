import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { ApiError, endpoints, type Bodega, type Rol, type Usuario } from "@/lib/api";

const ROLES: Rol[] = ["administrador", "supervisor", "supernumerario"];

export function Usuarios() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [msg, setMsg] = useState<{ tipo: "ok" | "err"; texto: string } | null>(null);

  const [nombre, setNombre] = useState("");
  const [cedula, setCedula] = useState("");
  const [password, setPassword] = useState("");
  const [rol, setRol] = useState<Rol>("supernumerario");
  const [bodegaIds, setBodegaIds] = useState<number[]>([]);

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
          <CardContent>
            <Table>
              <THead>
                <TR>
                  <TH>Nombre</TH>
                  <TH>Cédula</TH>
                  <TH>Rol</TH>
                  <TH>Bodegas</TH>
                  <TH>Estado</TH>
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
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
