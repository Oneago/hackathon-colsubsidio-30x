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
}

export interface Listado {
  id: number;
  toma_id: number;
  bodega_id: number;
  supernumerario_id: number | null;
  estado: "activo" | "completado" | "cancelado";
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
  items: (bodegaId: number) => api.get<Item[]>(`/bodegas/${bodegaId}/items`),

  tomas: () => api.get<Toma[]>("/tomas"),
  abrirToma: (bodega_id: number) => api.post<Toma>("/tomas", { bodega_id }),
  cerrarToma: (id: number) => api.post<Toma>(`/tomas/${id}/cerrar`),

  listados: (tomaId?: number) =>
    api.get<Listado[]>(`/listados${tomaId ? `?toma_id=${tomaId}` : ""}`),
  crearListado: (data: {
    toma_id: number;
    bodega_id: number;
    supernumerario_id: number;
    item_ids?: number[];
  }) => api.post<Listado>("/listados", data),

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
