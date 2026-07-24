import { Download } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { descargarArchivo, endpoints, type Comparacion, type Toma } from "@/lib/api";
import { cn } from "@/lib/utils";

function resumenChip(label: string, valor: number | string) {
  return (
    <div className="rounded-lg border bg-card px-4 py-3">
      <div className="text-2xl font-semibold tabular-nums">{valor}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

export function Reportes() {
  const [tomas, setTomas] = useState<Toma[]>([]);
  const [tomaId, setTomaId] = useState<number | null>(null);
  const [data, setData] = useState<Comparacion | null>(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    endpoints.tomas().then((ts) => {
      setTomas(ts);
      if (ts.length) setTomaId(ts[0].id);
    });
  }, []);

  useEffect(() => {
    if (tomaId == null) return;
    setCargando(true);
    endpoints
      .comparacion(tomaId)
      .then(setData)
      .finally(() => setCargando(false));
  }, [tomaId]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Comparación ERP vs. conteo</h1>

      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1.5">
          <Label>Toma</Label>
          <Select
            className="w-80"
            value={tomaId ?? ""}
            onChange={(e) => setTomaId(Number(e.target.value))}
          >
            {tomas.map((t) => (
              <option key={t.id} value={t.id}>
                Toma #{t.id} · {t.estado} · {new Date(t.fecha_apertura).toLocaleDateString("es-CO")}
              </option>
            ))}
          </Select>
        </div>
        {data && (
          <Button
            variant="outline"
            onClick={() =>
              descargarArchivo(
                `/reportes/comparacion.csv?toma_id=${data.toma_id}`,
                `comparacion_toma_${data.toma_id}.csv`,
              )
            }
          >
            <Download className="h-4 w-4" /> Exportar CSV
          </Button>
        )}
      </div>

      {data && (
        <>
          <div className="flex flex-wrap gap-3">
            {resumenChip("Ítems", data.resumen.total_items)}
            {resumenChip("Contados", data.resumen.contados)}
            {resumenChip("Pendientes", data.resumen.pendientes)}
            {resumenChip(`Críticos (≥${data.resumen.umbral_pct}%)`, data.resumen.criticos)}
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
                      <TD>{f.descripcion}</TD>
                      <TD className="text-right tabular-nums">{f.cantidad_erp}</TD>
                      <TD className="text-right tabular-nums">{f.cantidad_contada ?? "—"}</TD>
                      <TD className="text-right tabular-nums">{f.diff_abs ?? "—"}</TD>
                      <TD className="text-right tabular-nums">
                        {f.diff_pct != null ? `${f.diff_pct.toFixed(1)}%` : "—"}
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
