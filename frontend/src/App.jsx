import { Navigate, Route, Routes } from "react-router-dom";
import TopBar from "./components/TopBar";
import WorkflowNav from "./components/WorkflowNav";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import { StatusProvider, useAppStatus } from "./context/StatusContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Results from "./pages/Results";
import History from "./pages/History";
import HistoryDetail from "./pages/HistoryDetail";
import Enrichment from "./pages/Enrichment";
import Catalog from "./pages/Catalog";
import Matching from "./pages/Matching";
import Messages from "./pages/Messages";
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
  { path: "/messages", element: <Messages /> },
  { path: "/settings", element: <Settings /> },
  { path: "/account", element: <Account /> },
];

export default function App() {
  const { loading, user } = useAuth();
  if (loading) return null;

  if (!user) {
    // No point probing readiness before there is a token to probe with.
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <StatusProvider>
      <SignedInApp />
    </StatusProvider>
  );
}

function SignedInApp() {
  const { status } = useAppStatus();

  return (
    <>
      <TopBar />
      <WorkflowNav status={status} />
      <Routes>
        <Route path="/login" element={<Navigate to="/" replace />} />
        {PROTECTED_ROUTES.map(({ path, element }) => (
          <Route key={path} path={path} element={<ProtectedRoute>{element}</ProtectedRoute>} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
