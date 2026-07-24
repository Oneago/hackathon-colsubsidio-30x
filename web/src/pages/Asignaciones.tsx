import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { ApiError, endpoints, type Bodega, type Listado, type Toma, type Usuario } from "@/lib/api";

export function Asignaciones() {
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [tomas, setTomas] = useState<Toma[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [listados, setListados] = useState<Listado[]>([]);
  const [nuevaBodega, setNuevaBodega] = useState<number | null>(null);
  const [supSel, setSupSel] = useState<Record<number, number>>({});
  const [msg, setMsg] = useState<{ tipo: "ok" | "err"; texto: string } | null>(null);

  const bodegaNombre = useMemo(
    () => Object.fromEntries(bodegas.map((b) => [b.id, b.nombre])),
    [bodegas],
  );

  async function recargar() {
    const [bs, ts, ls] = await Promise.all([
      endpoints.bodegas(),
      endpoints.tomas(),
      endpoints.listados(),
    ]);
    setBodegas(bs);
    setTomas(ts);
    setListados(ls);
    const operativas = bs.filter((b) => b.es_operativa);
    if (nuevaBodega == null && operativas.length) setNuevaBodega(operativas[0].id);
  }

  useEffect(() => {
    recargar().catch(() => {});
    endpoints.usuarios().then(setUsuarios).catch(() => {
      /* supervisor no puede listar usuarios; se ignora */
    });
  }, []);

  function supernumerariosDe(bodegaId: number) {
    return usuarios.filter(
      (u) => u.rol === "supernumerario" && u.bodegas.some((b) => b.id === bodegaId),
    );
  }

  async function abrirToma(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (nuevaBodega == null) return;
    try {
      await endpoints.abrirToma(nuevaBodega);
      setMsg({ tipo: "ok", texto: "Toma abierta" });
      await recargar();
    } catch (err) {
      setMsg({ tipo: "err", texto: err instanceof ApiError ? err.message : "Error" });
    }
  }

  async function cerrarToma(id: number) {
    setMsg(null);
    try {
      await endpoints.cerrarToma(id);
      await recargar();
    } catch (err) {
      setMsg({ tipo: "err", texto: err instanceof ApiError ? err.message : "Error" });
    }
  }

  async function asignar(toma: Toma) {
    setMsg(null);
    const supId = supSel[toma.id];
    if (!supId) {
      setMsg({ tipo: "err", texto: "Selecciona un supernumerario" });
      return;
    }
    try {
      await endpoints.crearListado({
        toma_id: toma.id,
        bodega_id: toma.bodega_id,
        supernumerario_id: supId,
      });
      setMsg({ tipo: "ok", texto: "Listado asignado" });
      await recargar();
    } catch (err) {
      // El bloqueo de concurrencia devuelve 409 con mensaje claro.
      setMsg({ tipo: "err", texto: err instanceof ApiError ? err.message : "Error" });
    }
  }

  const operativas = bodegas.filter((b) => b.es_operativa);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Tomas y asignaciones</h1>

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

      <Card>
        <CardHeader>
          <CardTitle>Abrir nueva toma</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={abrirToma} className="flex flex-wrap items-end gap-4">
            <div className="space-y-1.5">
              <Label>Bodega operativa</Label>
              <Select
                className="w-72"
                value={nuevaBodega ?? ""}
                onChange={(e) => setNuevaBodega(Number(e.target.value))}
              >
                {operativas.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.nombre}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="submit">Abrir toma</Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tomas ({tomas.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {tomas.map((t) => {
            const susListados = listados.filter((l) => l.toma_id === t.id);
            const sups = supernumerariosDe(t.bodega_id);
            return (
              <div key={t.id} className="rounded-lg border p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{bodegaNombre[t.bodega_id] ?? `Bodega ${t.bodega_id}`}</div>
                    <div className="text-xs text-muted-foreground">
                      Toma #{t.id} · abierta {new Date(t.fecha_apertura).toLocaleString("es-CO")}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={t.estado === "abierta" ? "success" : "secondary"}>{t.estado}</Badge>
                    {t.estado === "abierta" && (
                      <Button variant="outline" size="sm" onClick={() => cerrarToma(t.id)}>
                        Cerrar toma
                      </Button>
                    )}
                  </div>
                </div>

                {t.estado === "abierta" && (
                  <div className="mt-3 flex flex-wrap items-end gap-3 border-t pt-3">
                    <div className="space-y-1.5">
                      <Label>Asignar a supernumerario</Label>
                      <Select
                        className="w-64"
                        value={supSel[t.id] ?? ""}
                        onChange={(e) => setSupSel((s) => ({ ...s, [t.id]: Number(e.target.value) }))}
                      >
                        <option value="">— seleccionar —</option>
                        {sups.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.nombre} ({u.cedula})
                          </option>
                        ))}
                      </Select>
                    </div>
                    <Button size="sm" onClick={() => asignar(t)}>
                      Asignar listado
                    </Button>
                    {sups.length === 0 && (
                      <span className="text-xs text-muted-foreground">
                        No hay supernumerarios en esta bodega.
                      </span>
                    )}
                  </div>
                )}

                {susListados.length > 0 && (
                  <Table className="mt-3">
                    <THead>
                      <TR>
                        <TH>Listado</TH>
                        <TH>Supernumerario</TH>
                        <TH>Estado</TH>
                        <TH className="text-right">Avance</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {susListados.map((l) => {
                        const sup = usuarios.find((u) => u.id === l.supernumerario_id);
                        return (
                          <TR key={l.id}>
                            <TD>#{l.id}</TD>
                            <TD>{sup ? sup.nombre : l.supernumerario_id}</TD>
                            <TD>
                              <Badge variant={l.estado === "activo" ? "default" : "secondary"}>
                                {l.estado}
                              </Badge>
                            </TD>
                            <TD className="text-right tabular-nums">
                              {l.contados}/{l.total_items}
                            </TD>
                          </TR>
                        );
                      })}
                    </TBody>
                  </Table>
                )}
              </div>
            );
          })}
          {tomas.length === 0 && <p className="text-sm text-muted-foreground">Aún no hay tomas.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
