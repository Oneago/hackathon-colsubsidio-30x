/** Codificador Code 128 → patrón de módulos, para dibujar el código en SVG.
 *
 * Implementado a mano en lugar de traer una librería porque es la única pieza
 * que la web necesita del asunto y así el bundle no depende de nada externo
 * (la consola debe poder imprimir etiquetas sin CDN).
 *
 * Code 128 es la simbología correcta para este dataset: los códigos no son EAN
 * reales sino valores internos del ERP, mezcla de numéricos (`7290`) y
 * sintéticos alfanuméricos (`GEN-a1b2c3d4e5`). Code 128 codifica ASCII
 * completo, a diferencia de EAN-13, y `mobile_scanner` lo lee por defecto.
 */

// Patrones de los 107 símbolos (0–102 datos, 103–105 arranques, 106 parada).
// Cada cadena alterna barra/espacio empezando por barra: '1' = módulo pintado.
const PATRONES = [
  "11011001100", "11001101100", "11001100110", "10010011000", "10010001100",
  "10001001100", "10011001000", "10011000100", "10001100100", "11001001000",
  "11001000100", "11000100100", "10110011100", "10011011100", "10011001110",
  "10111001100", "10011101100", "10011100110", "11001110010", "11001011100",
  "11001001110", "11011100100", "11001110100", "11101101110", "11101001100",
  "11100101100", "11100100110", "11101100100", "11100110100", "11100110010",
  "11011011000", "11011000110", "11000110110", "10100011000", "10001011000",
  "10001000110", "10110001000", "10001101000", "10001100010", "11010001000",
  "11000101000", "11000100010", "10110111000", "10110001110", "10001101110",
  "10111011000", "10111000110", "10001110110", "11101110110", "11010001110",
  "11000101110", "11011101000", "11011100010", "11011101110", "11101011000",
  "11101000110", "11100010110", "11101101000", "11101100010", "11100011010",
  "11101111010", "11001000010", "11110001010", "10100110000", "10100001100",
  "10010110000", "10010000110", "10000101100", "10000100110", "10110010000",
  "10110000100", "10011010000", "10011000010", "10000110100", "10000110010",
  "11000010010", "11001010000", "11110111010", "11000010100", "10001111010",
  "10100111100", "10010111100", "10010011110", "10111100100", "10011110100",
  "10011110010", "11110100100", "11110010100", "11110010010", "11011011110",
  "11011110110", "11110110110", "10101111000", "10100011110", "10001011110",
  "10111101000", "10111100010", "11110101000", "11110100010", "10111011110",
  "10111101110", "11101011110", "11110101110", "11010000100", "11010010000",
  "11010011100", "1100011101011",
];

const INICIO_B = 104;
const INICIO_C = 105;
const PARADA = 106;

/** Zona muda: sin este margen en blanco el lector no reconoce el símbolo. */
export const ZONA_MUDA = 10;

export class Code128Error extends Error {}

function esNumericoPar(texto: string): boolean {
  return texto.length > 0 && texto.length % 2 === 0 && /^\d+$/.test(texto);
}

/** Valores de los símbolos de datos, eligiendo el subconjunto más compacto. */
function valores(texto: string): number[] {
  // Subconjunto C empaqueta dos dígitos por símbolo: para códigos numéricos
  // pares deja la etiqueta a la mitad de ancho. El resto va por B, que cubre
  // todo el ASCII imprimible (incluye los sintéticos `GEN-…`).
  if (esNumericoPar(texto)) {
    const vals = [INICIO_C];
    for (let i = 0; i < texto.length; i += 2) vals.push(Number(texto.slice(i, i + 2)));
    return vals;
  }

  const vals = [INICIO_B];
  for (const ch of texto) {
    const code = ch.charCodeAt(0);
    if (code < 32 || code > 126) {
      throw new Code128Error(`El código «${texto}» tiene un carácter no imprimible y no se puede codificar`);
    }
    vals.push(code - 32);
  }
  return vals;
}

/**
 * Devuelve el patrón de módulos ('1' pintado, '0' en blanco) de `texto`,
 * incluyendo arranque, dígito de control y parada — pero NO la zona muda.
 */
export function patronCode128(texto: string): string {
  if (!texto) throw new Code128Error("El código está vacío");

  const vals = valores(texto);
  // Control módulo 103: arranque + Σ(posición × valor), posición desde 1.
  let suma = vals[0];
  for (let i = 1; i < vals.length; i += 1) suma += i * vals[i];
  vals.push(suma % 103);
  vals.push(PARADA);

  return vals.map((v) => PATRONES[v]).join("");
}

/** Barras contiguas del patrón, como {x, ancho} en unidades de módulo. */
export interface Barra {
  x: number;
  ancho: number;
}

/**
 * Ancho de módulo (dimensión X) por debajo del cual un lector empieza a fallar,
 * en mm. Los códigos sintéticos `GEN-<sha1>` del dataset ocupan ~189 módulos:
 * apretados en una etiqueta pequeña caen bajo este umbral y no se leen.
 */
export const MODULO_MINIMO_MM = 0.25;

export function barrasCode128(texto: string): { barras: Barra[]; modulos: number } {
  const patron = patronCode128(texto);
  const barras: Barra[] = [];
  let i = 0;
  while (i < patron.length) {
    if (patron[i] === "1") {
      const inicio = i;
      while (i < patron.length && patron[i] === "1") i += 1;
      barras.push({ x: ZONA_MUDA + inicio, ancho: i - inicio });
    } else {
      i += 1;
    }
  }
  return { barras, modulos: patron.length + ZONA_MUDA * 2 };
}
