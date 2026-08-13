import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function TopBar() {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <header className="topbar">
      <NavLink className="brand" to="/">
        ABIM Sales Assistant
      </NavLink>
      <nav>
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
          Search
        </NavLink>
        <NavLink to="/history" className={({ isActive }) => (isActive ? "active" : "")}>
          History
        </NavLink>
        <NavLink to="/account" className={({ isActive }) => (isActive ? "active" : "")}>
          Account
        </NavLink>
        <button className="link-button" onClick={logout}>
          Log out
        </button>
      </nav>
    </header>
  );
}
