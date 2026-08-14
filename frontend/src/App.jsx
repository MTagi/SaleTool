import { Navigate, Route, Routes } from "react-router-dom";
import TopBar from "./components/TopBar";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Results from "./pages/Results";
import History from "./pages/History";
import HistoryDetail from "./pages/HistoryDetail";
import Enrichment from "./pages/Enrichment";
import Catalog from "./pages/Catalog";
import Matching from "./pages/Matching";
import Settings from "./pages/Settings";
import Account from "./pages/Account";

const PROTECTED_ROUTES = [
  { path: "/", element: <Dashboard /> },
  { path: "/results", element: <Results /> },
  { path: "/history", element: <History /> },
  { path: "/history/:runId", element: <HistoryDetail /> },
  { path: "/enrichment", element: <Enrichment /> },
  { path: "/catalog", element: <Catalog /> },
  { path: "/matching", element: <Matching /> },
  { path: "/settings", element: <Settings /> },
  { path: "/account", element: <Account /> },
];

export default function App() {
  const { loading } = useAuth();
  if (loading) return null;

  return (
    <>
      <TopBar />
      <Routes>
        <Route path="/login" element={<LoginOrRedirect />} />
        {PROTECTED_ROUTES.map(({ path, element }) => (
          <Route key={path} path={path} element={<ProtectedRoute>{element}</ProtectedRoute>} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

function LoginOrRedirect() {
  const { user } = useAuth();
  if (user) return <Navigate to="/" replace />;
  return <Login />;
}
