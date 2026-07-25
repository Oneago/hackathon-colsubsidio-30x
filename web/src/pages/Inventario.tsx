import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { endpoints, type Bodega, type Item } from "@/lib/api";
import { formatearCantidad } from "@/lib/utils";

export function Inventario() {
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [bodegaId, setBodegaId] = useState<number | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [filtro, setFiltro] = useState("");
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    endpoints.bodegas(true).then((bs) => {
      setBodegas(bs);
      if (bs.length) setBodegaId(bs[0].id);
    });
  }, []);

  useEffect(() => {
    if (bodegaId == null) return;
    setCargando(true);
    endpoints
      .items(bodegaId)
      .then(setItems)
      .finally(() => setCargando(false));
  }, [bodegaId]);

  const visibles = items.filter(
    (i) => i.descripcion.toLowerCase().includes(filtro.toLowerCase()) || i.codigo_barras.includes(filtro),
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Inventario por bodega</h1>

      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1.5">
          <Label>Bodega</Label>
          <Select
            className="w-72"
            value={bodegaId ?? ""}
            onChange={(e) => setBodegaId(Number(e.target.value))}
          >
            {bodegas.map((b) => (
              <option key={b.id} value={b.id}>
                {b.nombre}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Buscar</Label>
          <Input
            className="w-72"
            placeholder="Descripción o código…"
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
          />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {cargando ? "Cargando…" : `${visibles.length} ítems`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Código</TH>
                <TH>Descripción</TH>
                <TH>Unidad</TH>
                <TH className="text-right">Cantidad ERP</TH>
              </TR>
            </THead>
            <TBody>
              {visibles.slice(0, 300).map((i) => (
                <TR key={i.id}>
                  <TD className="font-mono text-xs">{i.codigo_barras}</TD>
                  <TD>{i.descripcion}</TD>
                  <TD className="capitalize text-muted-foreground">{i.unidad}</TD>
                  <TD className="text-right tabular-nums">{formatearCantidad(i.cantidad_erp)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
          {visibles.length > 300 && (
            <p className="mt-3 text-xs text-muted-foreground">
              Mostrando 300 de {visibles.length}. Refina la búsqueda.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
