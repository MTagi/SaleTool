import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const groups = [
  ["Workspace", [["/", "Search", "⌕"], ["/enrichment", "Enrichment", "◇"], ["/matching", "Matching", "⇄"], ["/messages", "Messages", "✉"], ["/history", "History", "◷"]]],
  ["Manage", [["/catalog", "Service catalog", "▦"], ["/settings", "Settings", "⚙"]]],
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  return <aside className="app-sidebar">
    <NavLink className="sidebar-brand" to="/">ABIM<span>Sales Assistant</span></NavLink>
    <nav aria-label="Main navigation">
      {groups.map(([title, items]) => <div className="sidebar-group" key={title}>
        <p>{title}</p>
        {items.map(([to, label, icon]) => <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => isActive || (to === "/" && pathname === "/results") ? "active" : undefined}>
          <span className="nav-icon" aria-hidden="true">{icon}</span>{label}
        </NavLink>)}
      </div>)}
    </nav>
    <div className="sidebar-account">
      <NavLink to="/account"><span className="account-avatar">{String(user || "A").slice(0, 1).toUpperCase()}</span><span>{user}<small>My account</small></span></NavLink>
      <button className="link-button" onClick={logout}>Log out</button>
    </div>
  </aside>;
}
