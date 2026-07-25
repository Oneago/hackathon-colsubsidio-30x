import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Da formato a una cantidad para mostrarla: coma decimal, sin ceros de cola.
 * Ej.: "5.000" -> "5", "5.483" -> "5,483", "5.900" -> "5,9". */
export function formatearCantidad(
  valor: string | number | null | undefined,
  decimales = 3,
  placeholder = "—",
): string {
  if (valor == null) return placeholder;
  let texto = typeof valor === "number" ? valor.toFixed(decimales) : valor;
  // Evita el "-0" engañoso (ej. diff_pct muy pequeño y negativo).
  if (/^-?0+(\.0+)?$/.test(texto)) texto = texto.replace(/^-/, "");
  if (texto.includes(".")) texto = texto.replace(/0+$/, "").replace(/\.$/, "");
  return texto.replace(".", ",");
}
