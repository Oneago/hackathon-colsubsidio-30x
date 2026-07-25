import { createBrowserRouter, Navigate } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { Login } from "@/pages/Login";
import { Usuarios } from "@/pages/Usuarios";
import { Inventario } from "@/pages/Inventario";
import { Asignaciones } from "@/pages/Asignaciones";
import { Reportes } from "@/pages/Reportes";
import { Etiquetas } from "@/pages/Etiquetas";

export const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/inventario" replace /> },
      { path: "usuarios", element: <Usuarios /> },
      { path: "inventario", element: <Inventario /> },
      { path: "asignaciones", element: <Asignaciones /> },
      { path: "reportes", element: <Reportes /> },
      { path: "etiquetas", element: <Etiquetas /> },
    ],
  },
]);
