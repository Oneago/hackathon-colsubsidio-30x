import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { ApiError, endpoints, type Bodega, type Listado, type Toma, type Usuario } from "@/lib/api";

function mensajeDeError(err: unknown): string {
  return err instanceof ApiError ? err.message : "No se pudo completar la operación";
}

export function Asignaciones() {
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [tomas, setTomas] = useState<Toma[]>([]);
  const [supers, setSupers] = useState<Usuario[]>([]);
  const [listados, setListados] = useState<Listado[]>([]);
  const [nuevaBodega, setNuevaBodega] = useState<number | null>(null);
  const [supSel, setSupSel] = useState<Record<number, number>>({});
  const [msg, setMsg] = useState<{ tipo: "ok" | "err"; texto: string } | null>(null);
  const [cargando, setCargando] = useState(true);
  // Listado que se está reasignando en el modal, y el destino elegido.
  const [reasignando, setReasignando] = useState<Listado | null>(null);
  const [destino, setDestino] = useState<number | "">("");

  const bodegaNombre = useMemo(
    () => Object.fromEntries(bodegas.map((b) => [b.id, b.nombre])),
    [bodegas],
  );

  async function recargar() {
    const [bs, ts, ls, sup] = await Promise.all([
      endpoints.bodegas(),
      endpoints.tomas(),
      endpoints.listados(),
      // Ruta acotada al alcance del usuario: el supervisor no puede leer /usuarios.
      endpoints.supernumerarios(),
    ]);
    setBodegas(bs);
    setTomas(ts);
    setListados(ls);
    setSupers(sup);
    const operativas = bs.filter((b) => b.es_operativa);
    if (nuevaBodega == null && operativas.length) setNuevaBodega(operativas[0].id);
  }

  useEffect(() => {
    recargar()
      .catch((err) => setMsg({ tipo: "err", texto: mensajeDeError(err) }))
      .finally(() => setCargando(false));
  }, []);

  function supernumerariosDe(bodegaId: number) {
    return supers.filter((u) => u.bodegas.some((b) => b.id === bodegaId));
  }

  /** Ejecuta una acción y refresca; centraliza el manejo de errores de la página. */
  async function ejecutar(accion: () => Promise<unknown>, exito: string) {
    setMsg(null);
    try {
      await accion();
      await recargar();
      setMsg({ tipo: "ok", texto: exito });
      return true;
    } catch (err) {
      setMsg({ tipo: "err", texto: mensajeDeError(err) });
      return false;
    }
  }

  async function abrirToma(e: React.FormEvent) {
    e.preventDefault();
    if (nuevaBodega == null) return;
    await ejecutar(() => endpoints.abrirToma(nuevaBodega), "Toma abierta");
  }

  async function asignar(toma: Toma) {
    const supId = supSel[toma.id];
    if (!supId) {
      setMsg({ tipo: "err", texto: "Seleccione un supernumerario" });
      return;
    }
    const ok = await ejecutar(
      () =>
        endpoints.crearListado({
          toma_id: toma.id,
          bodega_id: toma.bodega_id,
          supernumerario_id: supId,
        }),
      "Listado asignado",
    );
    if (ok) setSupSel((s) => ({ ...s, [toma.id]: 0 }));
  }

  async function confirmarReasignacion() {
    if (!reasignando || destino === "") return;
    const ok = await ejecutar(
      () => endpoints.actualizarListado(reasignando.id, { supernumerario_id: Number(destino) }),
      "Listado reasignado",
    );
    if (ok) {
      setReasignando(null);
      setDestino("");
    }
  }

  const operativas = bodegas.filter((b) => b.es_operativa);
  // Un listado activo bloquea la bodega en esa toma: la UI lo dice antes de
  // que el usuario choque contra el 409 del servidor.
  const activoDe = (tomaId: number) =>
    listados.find((l) => l.toma_id === tomaId && l.estado === "activo");

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
                className="w-full sm:w-72"
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
            const activo = activoDe(t.id);
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
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          ejecutar(() => endpoints.cerrarToma(t.id), `Toma #${t.id} cerrada`)
                        }
                      >
                        Cerrar toma
                      </Button>
                    )}
                  </div>
                </div>

                {t.estado === "abierta" && !activo && (
                  <div className="mt-3 flex flex-wrap items-end gap-3 border-t pt-3">
                    <div className="space-y-1.5">
                      <Label>Asignar a supernumerario</Label>
                      <Select
                        className="w-full sm:w-64"
                        value={supSel[t.id] || ""}
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
                    <Button size="sm" onClick={() => asignar(t)} disabled={sups.length === 0}>
                      Asignar listado
                    </Button>
                    {sups.length === 0 && (
                      <span className="text-xs text-muted-foreground">
                        No hay supernumerarios activos en esta bodega.
                      </span>
                    )}
                  </div>
                )}

                {t.estado === "abierta" && activo && (
                  <div className="mt-3 flex flex-wrap items-center gap-3 border-t pt-3 text-sm">
                    <span className="text-muted-foreground">
                      Asignada a <strong className="text-foreground">{activo.supernumerario_nombre}</strong>{" "}
                      (listado #{activo.id})
                    </span>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setReasignando(activo);
                          setDestino("");
                        }}
                      >
                        Reasignar
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          ejecutar(
                            () => endpoints.actualizarListado(activo.id, { estado: "cancelado" }),
                            `Listado #${activo.id} cancelado`,
                          )
                        }
                      >
                        Cancelar listado
                      </Button>
                    </div>
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
                      {susListados.map((l) => (
                        <TR key={l.id}>
                          <TD>#{l.id}</TD>
                          <TD>{l.supernumerario_nombre ?? "—"}</TD>
                          <TD>
                            <Badge variant={l.estado === "activo" ? "default" : "secondary"}>
                              {l.estado}
                            </Badge>
                          </TD>
                          <TD className="text-right tabular-nums">
                            {l.contados}/{l.total_items}
                          </TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                )}
              </div>
            );
          })}
          {!cargando && tomas.length === 0 && (
            <p className="text-sm text-muted-foreground">Aún no hay tomas.</p>
          )}
          {cargando && <p className="text-sm text-muted-foreground">Cargando…</p>}
        </CardContent>
      </Card>

      <Dialog
        open={reasignando !== null}
        onClose={() => setReasignando(null)}
        title="Reasignar listado"
        description={
          reasignando
            ? `Listado #${reasignando.id} · ${reasignando.bodega_nombre}. Los conteos ya registrados se conservan.`
            : undefined
        }
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Nuevo supernumerario</Label>
            <Select
              className="w-full"
              value={destino}
              onChange={(e) => setDestino(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">— seleccionar —</option>
              {reasignando &&
                supernumerariosDe(reasignando.bodega_id)
                  .filter((u) => u.id !== reasignando.supernumerario_id)
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.nombre} ({u.cedula})
                    </option>
                  ))}
            </Select>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setReasignando(null)}>
              Cancelar
            </Button>
            <Button onClick={confirmarReasignacion} disabled={destino === ""}>
              Reasignar
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
