import { useMemo } from "react";

import { Code128Error, barrasCode128 } from "@/lib/code128";

interface Props {
  valor: string;
  /** Alto del símbolo en mm. La anchura la fija el contenedor. */
  altoMm?: number;
  className?: string;
}

/**
 * Código de barras Code 128 dibujado como SVG.
 *
 * Va en SVG y no en canvas/imagen porque la impresión lo rasteriza a la
 * resolución de la impresora: las barras salen nítidas a cualquier tamaño, que
 * es justo lo que un lector necesita.
 */
export function CodigoBarras({ valor, altoMm = 14, className }: Props) {
  const simbolo = useMemo(() => {
    try {
      return barrasCode128(valor);
    } catch (err) {
      return err instanceof Code128Error ? err.message : "Código no imprimible";
    }
  }, [valor]);

  if (typeof simbolo === "string") {
    return <p className="text-xs text-destructive">{simbolo}</p>;
  }

  return (
    <svg
      className={className}
      viewBox={`0 0 ${simbolo.modulos} 100`}
      // El símbolo se estira a lo ancho del contenedor; las proporciones
      // verticales no afectan la lectura.
      preserveAspectRatio="none"
      style={{ width: "100%", height: `${altoMm}mm`, display: "block" }}
      shapeRendering="crispEdges"
      role="img"
      aria-label={`Código de barras ${valor}`}
    >
      {/* Fondo blanco explícito: la zona muda tiene que imprimirse en blanco
          aunque la hoja herede algún color de fondo. */}
      <rect x="0" y="0" width={simbolo.modulos} height="100" fill="#fff" />
      {simbolo.barras.map((b) => (
        <rect key={b.x} x={b.x} y="0" width={b.ancho} height="100" fill="#000" />
      ))}
    </svg>
  );
}
