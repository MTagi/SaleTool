import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function TopBar() {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <header className="topbar">
      <Link className="brand" to="/">
        SaleTool
      </Link>
      <nav>
        <Link to="/history">Lịch sử</Link>
        <span className="user">{user}</span>
        <button className="link-button" onClick={logout}>
          Đăng xuất
        </button>
      </nav>
    </header>
  );
}
