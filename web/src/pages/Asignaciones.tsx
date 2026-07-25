import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import {
  ApiError,
  endpoints,
  type Bodega,
  type Item,
  type Listado,
  type Toma,
  type Usuario,
} from "@/lib/api";

function mensajeDeError(err: unknown): string {
  return err instanceof ApiError ? err.message : "No se pudo completar la operación";
}

export function Asignaciones() {
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [tomas, setTomas] = useState<Toma[]>([]);
  const [supers, setSupers] = useState<Usuario[]>([]);
  const [listados, setListados] = useState<Listado[]>([]);
  const [nuevaBodega, setNuevaBodega] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ tipo: "ok" | "err"; texto: string } | null>(null);
  const [cargando, setCargando] = useState(true);
  // Listado que se está reasignando en el modal, y el destino elegido.
  const [reasignando, setReasignando] = useState<Listado | null>(null);
  const [destino, setDestino] = useState<number | "">("");

  // Toma para la que se está armando una asignación en el modal, con su selector de ítems.
  const [asignando, setAsignando] = useState<Toma | null>(null);
  const [asignSupId, setAsignSupId] = useState<number | "">("");
  const [asignItems, setAsignItems] = useState<Item[]>([]);
  const [asignSeleccion, setAsignSeleccion] = useState<Set<number>>(new Set());
  const [asignBusqueda, setAsignBusqueda] = useState("");
  const [asignCargandoItems, setAsignCargandoItems] = useState(false);

  // Toma que se está por eliminar (confirmación pendiente).
  const [eliminando, setEliminando] = useState<Toma | null>(null);

  // Listado activo al que se le están agregando ítems, y los candidatos (los
  // que aún no están incluidos) cargados para el modal.
  const [agregando, setAgregando] = useState<Listado | null>(null);
  const [agregarCandidatos, setAgregarCandidatos] = useState<Item[]>([]);
  const [agregarSeleccion, setAgregarSeleccion] = useState<Set<number>>(new Set());
  const [agregarBusqueda, setAgregarBusqueda] = useState("");
  const [agregarCargando, setAgregarCargando] = useState(false);

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

  function abrirModalAsignar(toma: Toma) {
    setAsignando(toma);
    setAsignSupId("");
    setAsignBusqueda("");
    setAsignItems([]);
    setAsignSeleccion(new Set());
    setAsignCargandoItems(true);
    endpoints
      .items(toma.bodega_id)
      .then((its) => {
        setAsignItems(its);
        // Todos seleccionados por defecto: el supervisor desmarca lo que no quiere incluir.
        setAsignSeleccion(new Set(its.map((i) => i.id)));
      })
      .catch((err) => setMsg({ tipo: "err", texto: mensajeDeError(err) }))
      .finally(() => setAsignCargandoItems(false));
  }

  function alternarAsignItem(id: number) {
    setAsignSeleccion((s) => {
      const nuevo = new Set(s);
      if (nuevo.has(id)) nuevo.delete(id);
      else nuevo.add(id);
      return nuevo;
    });
  }

  const asignFiltrados = useMemo(() => {
    const q = asignBusqueda.trim().toLowerCase();
    if (!q) return asignItems;
    return asignItems.filter(
      (i) => i.descripcion.toLowerCase().includes(q) || i.codigo_barras.toLowerCase().includes(q),
    );
  }, [asignItems, asignBusqueda]);

  async function confirmarAsignacion() {
    if (!asignando || !asignSupId) return;
    const ok = await ejecutar(
      () =>
        endpoints.crearListado({
          toma_id: asignando.id,
          bodega_id: asignando.bodega_id,
          supernumerario_id: Number(asignSupId),
          item_ids: Array.from(asignSeleccion),
        }),
      "Listado asignado",
    );
    if (ok) setAsignando(null);
  }

  async function confirmarEliminacion() {
    if (!eliminando) return;
    const ok = await ejecutar(
      () => endpoints.eliminarToma(eliminando.id),
      `Toma #${eliminando.id} eliminada`,
    );
    if (ok) setEliminando(null);
  }

  function abrirModalAgregar(listado: Listado) {
    setAgregando(listado);
    setAgregarBusqueda("");
    setAgregarSeleccion(new Set());
    setAgregarCandidatos([]);
    setAgregarCargando(true);
    Promise.all([endpoints.items(listado.bodega_id), endpoints.itemsDeListado(listado.id)])
      .then(([todos, incluidos]) => {
        const incluidosIds = new Set(incluidos.map((i) => i.id));
        setAgregarCandidatos(todos.filter((i) => !incluidosIds.has(i.id)));
      })
      .catch((err) => setMsg({ tipo: "err", texto: mensajeDeError(err) }))
      .finally(() => setAgregarCargando(false));
  }

  function alternarAgregarItem(id: number) {
    setAgregarSeleccion((s) => {
      const nuevo = new Set(s);
      if (nuevo.has(id)) nuevo.delete(id);
      else nuevo.add(id);
      return nuevo;
    });
  }

  const agregarFiltrados = useMemo(() => {
    const q = agregarBusqueda.trim().toLowerCase();
    if (!q) return agregarCandidatos;
    return agregarCandidatos.filter(
      (i) => i.descripcion.toLowerCase().includes(q) || i.codigo_barras.toLowerCase().includes(q),
    );
  }, [agregarCandidatos, agregarBusqueda]);

  async function confirmarAgregarItems() {
    if (!agregando || agregarSeleccion.size === 0) return;
    const ok = await ejecutar(
      () => endpoints.agregarItemsListado(agregando.id, Array.from(agregarSeleccion)),
      `Ítems agregados al listado #${agregando.id}`,
    );
    if (ok) setAgregando(null);
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
                    {t.estado === "cerrada" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          ejecutar(() => endpoints.reabrirToma(t.id), `Toma #${t.id} reabierta`)
                        }
                      >
                        Reabrir toma
                      </Button>
                    )}
                    <Button variant="destructive" size="sm" onClick={() => setEliminando(t)}>
                      Eliminar toma
                    </Button>
                  </div>
                </div>

                {t.estado === "abierta" && !activo && (
                  <div className="mt-3 flex flex-wrap items-center gap-3 border-t pt-3">
                    <Button size="sm" onClick={() => abrirModalAsignar(t)} disabled={sups.length === 0}>
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
                      <Button variant="outline" size="sm" onClick={() => abrirModalAgregar(activo)}>
                        Agregar ítems
                      </Button>
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
                        <TH />
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
                          <TD className="text-right">
                            {t.estado === "abierta" && !activo && l.estado === "completado" && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  ejecutar(
                                    () => endpoints.actualizarListado(l.id, { estado: "activo" }),
                                    `Listado #${l.id} reactivado`,
                                  )
                                }
                              >
                                Reactivar
                              </Button>
                            )}
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

      <Dialog
        open={asignando !== null}
        onClose={() => setAsignando(null)}
        title="Asignar listado"
        description={
          asignando ? `${bodegaNombre[asignando.bodega_id] ?? `Bodega ${asignando.bodega_id}`} · toma #${asignando.id}` : undefined
        }
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Supernumerario</Label>
            <Select
              className="w-full"
              value={asignSupId}
              onChange={(e) => setAsignSupId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">— seleccionar —</option>
              {asignando &&
                supernumerariosDe(asignando.bodega_id).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nombre} ({u.cedula})
                  </option>
                ))}
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Ítems a incluir</Label>
            <Input
              placeholder="Descripción o código…"
              value={asignBusqueda}
              onChange={(e) => setAsignBusqueda(e.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="text-muted-foreground">
              {asignSeleccion.size} de {asignItems.length} seleccionados
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAsignSeleccion(new Set(asignFiltrados.map((i) => i.id)))}
            >
              Seleccionar {asignBusqueda ? "lo filtrado" : "todo"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setAsignSeleccion(new Set())}>
              Quitar todo
            </Button>
          </div>

          {asignCargandoItems && <p className="text-sm text-muted-foreground">Cargando ítems…</p>}
          {!asignCargandoItems && asignFiltrados.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {asignItems.length === 0 ? "Esta bodega no tiene ítems." : "Ningún ítem coincide con la búsqueda."}
            </p>
          )}
          {asignFiltrados.length > 0 && (
            <div className="max-h-72 overflow-y-auto rounded-md border">
              {asignFiltrados.map((i) => (
                <label
                  key={i.id}
                  className="flex cursor-pointer items-center gap-3 border-b px-3 py-2 text-sm last:border-b-0 hover:bg-accent"
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-primary"
                    checked={asignSeleccion.has(i.id)}
                    onChange={() => alternarAsignItem(i.id)}
                  />
                  <span className="font-mono text-xs text-muted-foreground">{i.codigo_barras}</span>
                  <span className="truncate">{i.descripcion}</span>
                </label>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setAsignando(null)}>
              Cancelar
            </Button>
            <Button
              onClick={confirmarAsignacion}
              disabled={!asignSupId || asignSeleccion.size === 0}
            >
              Asignar listado
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={agregando !== null}
        onClose={() => setAgregando(null)}
        title="Agregar ítems"
        description={agregando ? `Listado #${agregando.id} · ${agregando.bodega_nombre}` : undefined}
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Buscar</Label>
            <Input
              placeholder="Descripción o código…"
              value={agregarBusqueda}
              onChange={(e) => setAgregarBusqueda(e.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="text-muted-foreground">{agregarSeleccion.size} seleccionados</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAgregarSeleccion(new Set(agregarFiltrados.map((i) => i.id)))}
            >
              Seleccionar {agregarBusqueda ? "lo filtrado" : "todo"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setAgregarSeleccion(new Set())}>
              Quitar todo
            </Button>
          </div>

          {agregarCargando && <p className="text-sm text-muted-foreground">Cargando ítems…</p>}
          {!agregarCargando && agregarFiltrados.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {agregarCandidatos.length === 0
                ? "Todos los ítems de la bodega ya están incluidos en este listado."
                : "Ningún ítem coincide con la búsqueda."}
            </p>
          )}
          {agregarFiltrados.length > 0 && (
            <div className="max-h-72 overflow-y-auto rounded-md border">
              {agregarFiltrados.map((i) => (
                <label
                  key={i.id}
                  className="flex cursor-pointer items-center gap-3 border-b px-3 py-2 text-sm last:border-b-0 hover:bg-accent"
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-primary"
                    checked={agregarSeleccion.has(i.id)}
                    onChange={() => alternarAgregarItem(i.id)}
                  />
                  <span className="font-mono text-xs text-muted-foreground">{i.codigo_barras}</span>
                  <span className="truncate">{i.descripcion}</span>
                </label>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setAgregando(null)}>
              Cancelar
            </Button>
            <Button onClick={confirmarAgregarItems} disabled={agregarSeleccion.size === 0}>
              Agregar ítems ({agregarSeleccion.size})
            </Button>
          </div>
        </div>
      </Dialog>

      <ConfirmDialog
        open={eliminando !== null}
        onClose={() => setEliminando(null)}
        onConfirm={confirmarEliminacion}
        title="Eliminar toma"
        description={
          eliminando
            ? `Esta acción es irreversible. Se eliminará la toma #${eliminando.id} de ${
                bodegaNombre[eliminando.bodega_id] ?? `Bodega ${eliminando.bodega_id}`
              } junto con todos sus listados, ítems asignados y conteos registrados. El historial de comparación de esta toma se perderá.`
            : undefined
        }
        confirmLabel="Eliminar"
        variant="destructive"
      />
    </div>
  );
}
