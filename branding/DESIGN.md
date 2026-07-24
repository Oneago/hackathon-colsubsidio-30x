# DESIGN.md — Guía de diseño Colsubsidio (hackathon-colsubsidio-30x)

> Guía operativa para agentes y desarrolladores. Define **cómo** usar el branding de
> Colsubsidio de forma consistente y accesible. Si vas a generar UI, léela **antes**
> de escribir estilos. Ante la duda, prioriza los tokens y reglas de este documento
> por encima de valores ad-hoc.

## 1. Assets de marca

Ubicados en `branding/`:

| Archivo | Uso |
| --- | --- |
| `LogoV1.png` | Logo principal. Úsalo por defecto. |
| `Logov2.png` | Variante secundaria. Úsalo cuando V1 no encaje (fondos, proporción). |
| `Colores Oficiales.png` | Referencia visual de la paleta oficial. |
| `gemini-code-1784828851602.html` | Guía cromática fuente (Pantone/CMYK/RGB/HEX). |

**Reglas de logo**
- No deformar, rotar ni recolorear el logo. Escalar siempre proporcionalmente.
- Mantener un área de respeto (padding) mínima alrededor equivalente a la altura de la "C".
- Sobre fondos oscuros usa la variante que preserve legibilidad; nunca pongas el logo azul sobre azul.

## 2. Colores corporativos (fuente de verdad)

| Rol | Nombre | HEX | RGB | CMYK | Pantone |
| --- | --- | --- | --- | --- | --- |
| Primario / acento | Amarillo Colsubsidio | `#ffd000` | 255 / 208 / 0 | 0 / 18 / 100 / 0 | 109 C |
| Secundario / marca | Azul Colsubsidio | `#0067b1` | 0 / 103 / 177 | 90 / 55 / 0 / 0 | 2196 C |
| Neutro / texto | Grafito | `#575756` | 87 / 87 / 86 | 0 / 0 / 0 / 80 | Cool Gray 11 C |

Estos tres son los **únicos** colores de marca. Todo lo demás son tintes/sombras
derivados o neutros de sistema.

## 3. Escalas derivadas (tintes y sombras)

Generadas mezclando hacia blanco (tinte) o negro (sombra). Úsalas para estados,
fondos, bordes y jerarquía — no inventes intermedios.

### Amarillo
| Token | HEX |
| --- | --- |
| `amarillo-700` (sombra 60%) | `#997d00` |
| `amarillo-600` (sombra 80%) | `#cca600` |
| `amarillo-500` (**base**) | `#ffd000` |
| `amarillo-400` (80%) | `#ffd933` |
| `amarillo-300` (60%) | `#ffe366` |
| `amarillo-200` (40%) | `#ffec99` |
| `amarillo-100` (20%) | `#fff6cc` |

### Azul
| Token | HEX |
| --- | --- |
| `azul-700` (sombra 60%) | `#003e6a` |
| `azul-600` (sombra 80%) | `#00528e` |
| `azul-500` (**base**) | `#0067b1` |
| `azul-400` (80%) | `#3385c1` |
| `azul-300` (60%) | `#66a4d0` |
| `azul-200` (40%) | `#99c2e0` |
| `azul-100` (20%) | `#cce1ef` |

### Grafito (neutros de marca)
| Token | HEX |
| --- | --- |
| `grafito-700` (sombra 60%) | `#343434` |
| `grafito-600` (sombra 80%) | `#464645` |
| `grafito-500` (**base**) | `#575756` |
| `grafito-400` (80%) | `#797978` |
| `grafito-300` (60%) | `#9a9a9a` |
| `grafito-200` (40%) | `#bcbcbb` |
| `grafito-100` (20%) | `#dddddd` |

### Neutros de sistema (no de marca, para superficies)
| Token | HEX | Uso |
| --- | --- | --- |
| `fondo` | `#f8f9fa` | Fondo de página |
| `superficie` | `#ffffff` | Tarjetas, paneles |
| `borde` | `#dee2e6` | Separadores, bordes sutiles |
| `texto` | `#212529` | Texto principal sobre fondo claro |

## 4. Roles semánticos (cómo aplicar cada color)

- **Azul (`azul-500`) = color de marca / estructura.** Encabezados, barras de
  navegación, enlaces, botones primarios, iconografía principal.
- **Amarillo (`amarillo-500`) = acento y llamada a la acción destacada.** Botones
  de énfasis, badges, highlights, indicadores. Es un color de **atención**, no de
  fondo extenso. Úsalo con moderación (regla ~10% de la composición).
- **Grafito (`grafito-500`) = texto y neutros.** Texto secundario, iconos inactivos,
  bordes de énfasis.
- **Neutros de sistema** para superficies y fondos.

Botones (referencia):
- **Primario:** fondo `azul-500`, texto `#ffffff`, hover `azul-600`.
- **Acento/CTA:** fondo `amarillo-500`, texto `grafito-700`/negro, hover `amarillo-600`.
- **Secundario:** fondo transparente, borde `azul-500`, texto `azul-500`.

## 5. Accesibilidad y contraste (WCAG 2.1) — reglas obligatorias

Ratios reales de la paleta base:

| Color | vs blanco | vs negro |
| --- | --- | --- |
| Amarillo `#ffd000` | **1.47** ✗ | 14.27 ✓ |
| Azul `#0067b1` | 5.87 ✓ (AA normal, AAA grande) | 3.57 |
| Grafito `#575756` | 7.23 ✓ (AAA) | 2.90 |

Reglas:
- **Nunca** uses texto blanco sobre amarillo ni texto amarillo sobre blanco: falla
  contraste (1.47). Sobre amarillo, el texto va en **negro/grafito oscuro**.
- Texto normal requiere ratio ≥ 4.5:1; texto grande (≥18.66px bold / 24px) ≥ 3:1.
- Azul y grafito sobre blanco son seguros para texto. Azul sobre amarillo NO cumple
  para texto pequeño — evítalo salvo elementos grandes/decorativos.
- Estados de foco visibles siempre (outline `azul-500` de 2px o similar).

## 6. Tokens listos para usar (CSS)

```css
:root {
  /* Marca */
  --color-amarillo: #ffd000;
  --color-azul: #0067b1;
  --color-grafito: #575756;

  /* Amarillo */
  --amarillo-700: #997d00; --amarillo-600: #cca600; --amarillo-500: #ffd000;
  --amarillo-400: #ffd933; --amarillo-300: #ffe366; --amarillo-200: #ffec99; --amarillo-100: #fff6cc;
  /* Azul */
  --azul-700: #003e6a; --azul-600: #00528e; --azul-500: #0067b1;
  --azul-400: #3385c1; --azul-300: #66a4d0; --azul-200: #99c2e0; --azul-100: #cce1ef;
  /* Grafito */
  --grafito-700: #343434; --grafito-600: #464645; --grafito-500: #575756;
  --grafito-400: #797978; --grafito-300: #9a9a9a; --grafito-200: #bcbcbb; --grafito-100: #dddddd;

  /* Sistema */
  --fondo: #f8f9fa; --superficie: #ffffff; --borde: #dee2e6; --texto: #212529;

  /* Roles semánticos */
  --brand: var(--azul-500);
  --accent: var(--amarillo-500);
  --on-accent: var(--grafito-700);   /* texto sobre amarillo */
  --on-brand: #ffffff;               /* texto sobre azul */
}
```

Equivalente en JS/TS (para theming programático):

```ts
export const brand = {
  amarillo: "#ffd000",
  azul: "#0067b1",
  grafito: "#575756",
} as const;
```

## 7. Tipografía

No hay fuente corporativa definida en los assets. Usa un stack de sistema legible y
neutro hasta que se especifique una:

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
```

Jerarquía sugerida: títulos en `azul-500` y peso 600–700; cuerpo en `texto`/`grafito-500`.

## 8. Do / Don't (resumen para el agente)

**Hazlo**
- Usa solo los tres colores de marca y sus escalas derivadas.
- Reserva el amarillo para acentos y CTAs (~10% de la composición).
- Verifica contraste antes de fijar combinaciones de texto/fondo.
- Referencia los tokens (`--azul-500`, etc.), no HEX sueltos, en el código.

**No lo hagas**
- Texto blanco sobre amarillo, o amarillo sobre blanco.
- Fondos amplios en amarillo saturado.
- Recolorear o deformar el logo.
- Introducir colores fuera de la paleta sin justificación de accesibilidad.

---
_Fuente: guía cromática oficial Colsubsidio (`branding/gemini-code-1784828851602.html`).
Escalas y ratios de contraste calculados sobre los HEX base._
