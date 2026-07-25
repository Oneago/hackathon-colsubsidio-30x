import { Printer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { CodigoBarras } from "@/components/CodigoBarras";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ApiError, endpoints, type Bodega, type Item } from "@/lib/api";
import { MODULO_MINIMO_MM, barrasCode128 } from "@/lib/code128";

/** Ancho útil del símbolo en una hoja carta/A4 con los márgenes de `@page`. */
function anchoSimboloMm(columnas: number): number {
  const CONTENIDO_MM = 194; // 210 mm de ancho − 8 mm de margen a cada lado
  const SEPARACION_MM = 2.1; // gap-2
  const RELLENO_MM = 4.5; // p-2 a cada lado + borde
  return (CONTENIDO_MM - (columnas - 1) * SEPARACION_MM) / columnas - RELLENO_MM;
}

/** Etiquetas por fila en la hoja impresa. Menos columnas = código más ancho. */
const DENSIDADES = [
  { valor: 2, label: "2 por fila (grande)" },
  { valor: 3, label: "3 por fila (media)" },
  { valor: 4, label: "4 por fila (pequeña)" },
];

const COLUMNAS: Record<number, string> = {
  2: "grid-cols-2",
  3: "grid-cols-2 sm:grid-cols-3",
  4: "grid-cols-2 sm:grid-cols-4",
};

function mensajeDeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "No se pudo contactar la API. Verifique la conexión e intente de nuevo.";
}

export function Etiquetas() {
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [bodegaId, setBodegaId] = useState<number | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const [densidad, setDensidad] = useState(3);
  const [seleccion, setSeleccion] = useState<Set<number>>(new Set());
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    endpoints
      .bodegas(true)
      .then((bs) => {
        setBodegas(bs);
        if (bs.length) setBodegaId(bs[0].id);
        else setCargando(false);
      })
      .catch((err) => {
        setError(mensajeDeError(err));
        setCargando(false);
      });
  }, []);

  useEffect(() => {
    if (bodegaId == null) return;
    setCargando(true);
    setError(null);
    endpoints
      .items(bodegaId)
      .then((its) => {
        setItems(its);
        // Al cambiar de bodega la selección anterior deja de tener sentido.
        setSeleccion(new Set(its.map((i) => i.id)));
      })
      .catch((err) => {
        setItems([]);
        setError(mensajeDeError(err));
      })
      .finally(() => setCargando(false));
  }, [bodegaId]);

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) => i.descripcion.toLowerCase().includes(q) || i.codigo_barras.toLowerCase().includes(q),
    );
  }, [items, busqueda]);

  const aImprimir = useMemo(
    () => items.filter((i) => seleccion.has(i.id)),
    [items, seleccion],
  );

  function alternar(id: number) {
    setSeleccion((s) => {
      const nuevo = new Set(s);
      if (nuevo.has(id)) nuevo.delete(id);
      else nuevo.add(id);
      return nuevo;
    });
  }

  const bodegaNombre = bodegas.find((b) => b.id === bodegaId)?.nombre ?? "";

  // El código más largo manda: si ese no se lee, la hoja no sirve. Se avisa
  // antes de gastar papel, no después de que el lector falle en la bodega.
  const apretado = useMemo(() => {
    if (aImprimir.length === 0) return null;
    let peor = { codigo: "", modulos: 0 };
    for (const i of aImprimir) {
      try {
        const { modulos } = barrasCode128(i.codigo_barras);
        if (modulos > peor.modulos) peor = { codigo: i.codigo_barras, modulos };
      } catch {
        /* el código inválido ya se señala en su etiqueta */
      }
    }
    if (!peor.modulos) return null;
    const moduloMm = anchoSimboloMm(densidad) / peor.modulos;
    return moduloMm < MODULO_MINIMO_MM ? { ...peor, moduloMm } : null;
  }, [aImprimir, densidad]);

  return (
    <div className="space-y-6">
      <div className="no-imprimir space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Etiquetas para escanear</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Genera códigos de barras Code 128 imprimibles para pegar en los estantes. Son los
            mismos códigos que la app móvil espera al escanear.
          </p>
        </div>

        {error && (
          <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Qué imprimir</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-end gap-4">
              <div className="space-y-1.5">
                <Label>Bodega</Label>
                <Select
                  className="w-full sm:w-72"
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
                <Label>Tamaño</Label>
                <Select
                  className="w-full sm:w-52"
                  value={densidad}
                  onChange={(e) => setDensidad(Number(e.target.value))}
                >
                  {DENSIDADES.map((d) => (
                    <option key={d.valor} value={d.valor}>
                      {d.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Buscar</Label>
                <Input
                  className="w-full sm:w-64"
                  placeholder="Descripción o código…"
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                />
              </div>
              <Button onClick={() => window.print()} disabled={aImprimir.length === 0}>
                <Printer className="h-4 w-4" /> Imprimir ({aImprimir.length})
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-3 border-t pt-3 text-sm">
              <span className="text-muted-foreground">
                {aImprimir.length} de {items.length} seleccionados
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSeleccion(new Set(filtrados.map((i) => i.id)))}
              >
                Seleccionar {busqueda ? "lo filtrado" : "todo"}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setSeleccion(new Set())}>
                Quitar todo
              </Button>
            </div>

            {apretado && (
              <p className="rounded-md bg-brand-accent/20 px-3 py-2 text-sm text-brand-accent-foreground">
                A {densidad} por fila, el código más largo de la selección (
                <span className="font-mono">{apretado.codigo}</span>) queda con barras de{" "}
                {apretado.moduloMm.toFixed(2)} mm y puede no leerse. Use un tamaño más grande.
              </p>
            )}

            {cargando && <p className="text-sm text-muted-foreground">Cargando ítems…</p>}
            {!cargando && filtrados.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {items.length === 0
                  ? "Esta bodega no tiene ítems."
                  : "Ningún ítem coincide con la búsqueda."}
              </p>
            )}

            {filtrados.length > 0 && (
              <div className="max-h-72 overflow-y-auto rounded-md border">
                {filtrados.map((i) => (
                  <label
                    key={i.id}
                    className="flex cursor-pointer items-center gap-3 border-b px-3 py-2 text-sm last:border-b-0 hover:bg-accent"
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-primary"
                      checked={seleccion.has(i.id)}
                      onChange={() => alternar(i.id)}
                    />
                    <span className="font-mono text-xs text-muted-foreground">{i.codigo_barras}</span>
                    <span className="truncate">{i.descripcion}</span>
                  </label>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Hoja imprimible. En pantalla es una vista previa; al imprimir es lo
          único que sale (ver `@media print` en index.css). */}
      <div className="area-impresion">
        <div className="no-imprimir mb-3 text-sm font-medium text-muted-foreground">
          Vista previa ({aImprimir.length} etiquetas)
        </div>
        <div className={`grid gap-2 ${COLUMNAS[densidad]}`}>
          {aImprimir.map((i) => (
            <div
              key={i.id}
              className="etiqueta flex flex-col justify-between rounded-md border border-foreground/25 bg-white p-2"
            >
              <div className="mb-1 text-[11px] font-semibold uppercase leading-tight text-black">
                {i.descripcion}
              </div>
              <CodigoBarras valor={i.codigo_barras} altoMm={densidad === 2 ? 18 : 13} />
              <div className="mt-1 flex items-baseline justify-between gap-2">
                <span className="font-mono text-xs tracking-wider text-black">{i.codigo_barras}</span>
                {/* Solo la unidad de medida. La cantidad del ERP NUNCA va en la
                    etiqueta: quien cuenta en campo no debe verla (anti-sesgo). */}
                <span className="text-[10px] uppercase text-black/60">{i.unidad}</span>
              </div>
            </div>
          ))}
        </div>
        {aImprimir.length > 0 && (
          <p className="no-imprimir mt-3 text-xs text-muted-foreground">
            {bodegaNombre} · {aImprimir.length} etiquetas. Imprima al 100 % (sin «ajustar a la
            página») para que el lector reconozca las barras.
          </p>
        )}
      </div>
    </div>
  );
}
