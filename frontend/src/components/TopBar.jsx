import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  { to: "/", label: "Search", end: true },
  { to: "/enrichment", label: "Enrichment" },
  { to: "/history", label: "History" },
  { to: "/settings", label: "Settings" },
  { to: "/account", label: "Account" },
];

export default function TopBar() {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <header className="topbar">
      <NavLink className="brand" to="/">
        ABIM Sales Assistant
      </NavLink>
      <nav>
        {NAV_ITEMS.map(({ to, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            {label}
          </NavLink>
        ))}
        <button className="link-button" onClick={logout}>
          Log out
        </button>
      </nav>
    </header>
  );
}
