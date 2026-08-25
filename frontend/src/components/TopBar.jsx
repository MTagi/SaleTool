import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Only the things that are not part of the pipeline live here.
 *
 * The five pipeline pages moved into the workflow strip below the bar, because
 * a flat list of eight links said nothing about which order to use them in.
 */
const NAV_ITEMS = [
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
      <nav aria-label="Account and settings">
        {NAV_ITEMS.map(({ to, label }) => (
          <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : "")}>
            {label}
          </NavLink>
        ))}
        <span className="topbar-user" title="Signed in">
          {user}
        </span>
        <button className="link-button" onClick={logout}>
          Log out
        </button>
      </nav>
    </header>
  );
}
