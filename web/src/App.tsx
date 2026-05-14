import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "./store/auth";
import Layout from "./components/Layout";

const Login = lazy(() => import("./pages/Login"));
const Kiosk = lazy(() => import("./pages/Kiosk"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Mapa = lazy(() => import("./pages/Mapa"));
const Consultas = lazy(() => import("./pages/Consultas"));
const Facturacion = lazy(() => import("./pages/Facturacion"));
const DetalleMedidor = lazy(() => import("./pages/DetalleMedidor"));
const Anomalias = lazy(() => import("./pages/Anomalias"));

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = useAuthStore((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Suspense fallback={<div className="p-8">Cargando...</div>}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/kiosk" element={<Kiosk />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="mapa" element={<Mapa />} />
          <Route path="consultas" element={<Consultas />} />
          <Route path="facturacion" element={<Facturacion />} />
          <Route path="medidor/:id" element={<DetalleMedidor />} />
          <Route path="anomalias" element={<Anomalias />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
