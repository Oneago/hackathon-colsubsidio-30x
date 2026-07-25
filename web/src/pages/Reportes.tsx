import { Download } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import {
  ApiError,
  descargarArchivo,
  endpoints,
  type Bodega,
  type Comparacion,
  type Listado,
  type Toma,
} from "@/lib/api";
import { cn, formatearCantidad } from "@/lib/utils";

function resumenChip(label: string, valor: number | string) {
  return (
    <div className="rounded-lg border bg-card px-4 py-3">
      <div className="text-2xl font-semibold tabular-nums">{valor}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

function mensajeDeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  // Un fallo de red (API caída, CORS, dominio equivocado) no llega como
  // ApiError: sin este caso la página se quedaba en blanco sin explicación.
  return "No se pudo contactar la API. Verifique la conexión e intente de nuevo.";
}

export function Reportes() {
  const [tomas, setTomas] = useState<Toma[]>([]);
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [listados, setListados] = useState<Listado[]>([]);
  const [tomaId, setTomaId] = useState<number | null>(null);
  const [data, setData] = useState<Comparacion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const bodegaNombre = useMemo(
    () => Object.fromEntries(bodegas.map((b) => [b.id, b.nombre])),
    [bodegas],
  );
  const conListado = useMemo(
    () => new Set(listados.map((l) => l.toma_id)),
    [listados],
  );

  useEffect(() => {
    Promise.all([endpoints.tomas(), endpoints.bodegas(), endpoints.listados()])
      .then(([ts, bs, ls]) => {
        setTomas(ts);
        setBodegas(bs);
        setListados(ls);
        // La toma más reciente suele ser una recién abierta y sin listados: el
        // informe salía vacío y parecía roto. Se preselecciona la más reciente
        // que sí tenga algo que comparar.
        const ids = new Set(ls.map((l) => l.toma_id));
        const preferida = ts.find((t) => ids.has(t.id)) ?? ts[0];
        if (preferida) setTomaId(preferida.id);
        else setCargando(false);
      })
      .catch((err) => {
        setError(mensajeDeError(err));
        setCargando(false);
      });
  }, []);

  useEffect(() => {
    if (tomaId == null) return;
    setCargando(true);
    setError(null);
    endpoints
      .comparacion(tomaId)
      .then(setData)
      .catch((err) => {
        setData(null);
        setError(mensajeDeError(err));
      })
      .finally(() => setCargando(false));
  }, [tomaId]);

  async function exportar() {
    if (!data) return;
    try {
      await descargarArchivo(
        `/reportes/comparacion.csv?toma_id=${data.toma_id}`,
        `comparacion_toma_${data.toma_id}.csv`,
      );
    } catch (err) {
      setError(mensajeDeError(err));
    }
  }

  const sinTomas = !cargando && !error && tomas.length === 0;
  const sinDatos = data !== null && data.filas.length === 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Comparación ERP vs. conteo</h1>

      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}

      {sinTomas && (
        <p className="text-sm text-muted-foreground">
          Todavía no hay tomas de inventario. Abra una en «Tomas y asignaciones» para poder comparar.
        </p>
      )}

      {tomas.length > 0 && (
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <Label>Toma</Label>
            <Select
              className="w-full sm:w-96"
              value={tomaId ?? ""}
              onChange={(e) => setTomaId(Number(e.target.value))}
            >
              {tomas.map((t) => (
                <option key={t.id} value={t.id}>
                  {`Toma #${t.id} · ${bodegaNombre[t.bodega_id] ?? `Bodega ${t.bodega_id}`} · ${t.estado} · ${new Date(
                    t.fecha_apertura,
                  ).toLocaleDateString("es-CO")}${conListado.has(t.id) ? "" : " · sin asignar"}`}
                </option>
              ))}
            </Select>
          </div>
          {data && !sinDatos && (
            <Button variant="outline" onClick={exportar}>
              <Download className="h-4 w-4" /> Exportar CSV
            </Button>
          )}
        </div>
      )}

      {cargando && <p className="text-sm text-muted-foreground">Cargando…</p>}

      {data && sinDatos && !cargando && (
        <p className="rounded-md border border-dashed px-4 py-6 text-sm text-muted-foreground">
          La toma #{data.toma_id} ({data.bodega_nombre}) no tiene ningún listado asignado, así que no
          hay nada que comparar. Asígnele un listado a un supernumerario en «Tomas y asignaciones».
        </p>
      )}

      {data && !sinDatos && (
        <>
          <div className="flex flex-wrap gap-3">
            {resumenChip("Ítems", data.resumen.total_items)}
            {resumenChip("Contados", data.resumen.contados)}
            {resumenChip("Pendientes", data.resumen.pendientes)}
            {resumenChip(`Críticos (≥${formatearCantidad(data.resumen.umbral_pct, 1)}%)`, data.resumen.criticos)}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>
                {data.bodega_nombre} {cargando && "· cargando…"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <THead>
                  <TR>
                    <TH>Código</TH>
                    <TH>Descripción</TH>
                    <TH className="text-right">ERP</TH>
                    <TH className="text-right">Contado</TH>
                    <TH className="text-right">Δ</TH>
                    <TH className="text-right">Δ %</TH>
                    <TH>Estado</TH>
                  </TR>
                </THead>
                <TBody>
                  {data.filas.map((f) => (
                    <TR
                      key={f.item_id}
                      className={cn(
                        f.critico && "bg-destructive/10",
                        !f.contado && "text-muted-foreground",
                      )}
                    >
                      <TD className="font-mono text-xs">{f.codigo_barras}</TD>
                      <TD className="min-w-48">{f.descripcion}</TD>
                      <TD className="text-right tabular-nums">{formatearCantidad(f.cantidad_erp)}</TD>
                      <TD className="text-right tabular-nums">{formatearCantidad(f.cantidad_contada)}</TD>
                      <TD className="text-right tabular-nums">{formatearCantidad(f.diff_abs)}</TD>
                      <TD className="text-right tabular-nums">
                        {f.diff_pct != null ? `${formatearCantidad(f.diff_pct, 1)}%` : "—"}
                      </TD>
                      <TD>
                        {!f.contado ? (
                          <Badge variant="secondary">pendiente</Badge>
                        ) : f.critico ? (
                          <Badge variant="destructive">crítico</Badge>
                        ) : (
                          <Badge variant="success">ok</Badge>
                        )}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
