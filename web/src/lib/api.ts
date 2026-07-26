// Cliente de API. La URL base viene por variable de entorno (VITE_API_BASE_URL),
// nunca escrita a mano en los componentes.
export const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

const TOKEN_KEY = "inv_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = tokenStore.get();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* respuesta sin cuerpo JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, b?: unknown) => request<T>("POST", p, b),
  patch: <T>(p: string, b?: unknown) => request<T>("PATCH", p, b),
  delete: <T>(p: string) => request<T>("DELETE", p),
};

// ── Tipos (espejo del contrato de la API) ──────────────────
export type Rol = "administrador" | "supervisor" | "supernumerario";

export interface Bodega {
  id: number;
  id_erp: number | null;
  nombre: string;
  es_operativa: boolean;
}

export interface Usuario {
  id: number;
  nombre: string;
  cedula: string;
  rol: Rol;
  activo: boolean;
  must_change_password: boolean;
  bodegas: Bodega[];
}

export interface Item {
  id: number;
  nr_articulo: number | null;
  codigo_barras: string;
  descripcion: string;
  unidad: string;
  cantidad_erp: string;
}

export interface Toma {
  id: number;
  bodega_id: number;
  estado: "abierta" | "cerrada";
  fecha_apertura: string;
  fecha_cierre: string | null;
  /** Sello de aprobación tras revisar la comparación. Aceptar no cambia `estado`:
   *  la toma sigue cerrada. Pedir reconteo lo vuelve a dejar en null. */
  aceptada_en: string | null;
  aceptada_por: number | null;
  aceptada_por_nombre: string | null;
}

export type EstadoListado = "activo" | "completado" | "cancelado";

export interface Listado {
  id: number;
  toma_id: number;
  bodega_id: number;
  supernumerario_id: number | null;
  supernumerario_nombre: string | null;
  bodega_nombre: string;
  estado: EstadoListado;
  total_items: number;
  contados: number;
}

export interface ComparacionFila {
  item_id: number;
  codigo_barras: string;
  descripcion: string;
  unidad: string;
  cantidad_erp: string;
  cantidad_contada: string | null;
  contado: boolean;
  diff_abs: string | null;
  diff_pct: number | null;
  critico: boolean;
  contado_en: string | null;
  metodo: string | null;
  entrada: string | null;
}

export interface Comparacion {
  toma_id: number;
  bodega_id: number;
  bodega_nombre: string;
  estado: string;
  resumen: {
    total_items: number;
    contados: number;
    pendientes: number;
    criticos: number;
    umbral_pct: number;
  };
  filas: ComparacionFila[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  rol: Rol;
  nombre: string;
  must_change_password: boolean;
}

// ── Endpoints ──────────────────────────────────────────────
export const endpoints = {
  loginWeb: (cedula: string, password: string) =>
    api.post<LoginResponse>("/auth/login/web", { cedula, password }),
  me: () => api.get<Usuario>("/auth/me"),

  usuarios: () => api.get<Usuario[]>("/usuarios"),
  /** Supernumerarios asignables. A diferencia de `usuarios()`, el supervisor sí puede llamarlo. */
  supernumerarios: (bodegaId?: number) =>
    api.get<Usuario[]>(
      `/usuarios/supernumerarios${bodegaId != null ? `?bodega_id=${bodegaId}` : ""}`,
    ),
  crearUsuario: (data: {
    nombre: string;
    cedula: string;
    password: string;
    rol: Rol;
    bodega_ids: number[];
  }) => api.post<Usuario>("/usuarios", data),
  restablecerPassword: (id: number, password_nueva: string) =>
    api.post<Usuario>(`/usuarios/${id}/reset-password`, { password_nueva }),

  bodegas: (soloOperativas = false) =>
    api.get<Bodega[]>(`/bodegas?solo_operativas=${soloOperativas}`),
  /** Si se pasa `tomaId`, excluye los ítems ya cubiertos por un listado activo de esa toma. */
  items: (bodegaId: number, tomaId?: number) =>
    api.get<Item[]>(`/bodegas/${bodegaId}/items${tomaId != null ? `?toma_id=${tomaId}` : ""}`),

  tomas: () => api.get<Toma[]>("/tomas"),
  abrirToma: (bodega_id: number) => api.post<Toma>("/tomas", { bodega_id }),
  cerrarToma: (id: number) => api.post<Toma>(`/tomas/${id}/cerrar`),
  reabrirToma: (id: number) => api.post<Toma>(`/tomas/${id}/reabrir`),
  aceptarToma: (id: number) => api.post<Toma>(`/tomas/${id}/aceptar`),
  /** Reabre la toma y revive sus listados, para que vuelvan a la app de campo. */
  solicitarReconteo: (id: number) => api.post<Toma>(`/tomas/${id}/solicitar-reconteo`),
  eliminarToma: (id: number) => api.delete<void>(`/tomas/${id}`),

  listados: (tomaId?: number) =>
    api.get<Listado[]>(`/listados${tomaId ? `?toma_id=${tomaId}` : ""}`),
  crearListado: (data: {
    toma_id: number;
    bodega_id: number;
    supernumerario_id: number;
    item_ids?: number[];
  }) => api.post<Listado>("/listados", data),
  /** Reasigna el listado a otro supernumerario y/o cambia su estado (cancelar). */
  actualizarListado: (
    id: number,
    data: { supernumerario_id?: number; estado?: EstadoListado },
  ) => api.patch<Listado>(`/listados/${id}`, data),
  /** Agrega ítems nuevos a un listado activo; no permite quitar los ya incluidos. */
  agregarItemsListado: (id: number, item_ids: number[]) =>
    api.patch<Listado>(`/listados/${id}/items`, { item_ids }),

  comparacion: (tomaId: number) =>
    api.get<Comparacion>(`/reportes/comparacion?toma_id=${tomaId}`),
};

/** Descarga un archivo protegido (envía el JWT y fuerza la descarga en el navegador). */
export async function descargarArchivo(path: string, filename: string): Promise<void> {
  const token = tokenStore.get();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, `Error ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
