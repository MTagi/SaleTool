import { useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Account() {
  const { user, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setSuccess("Password updated.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err.message || "Couldn't update password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="container">
      <h1>Account</h1>

      <fieldset className="account-summary">
        <legend>Signed in as</legend>
        <p className="account-username">{user}</p>
      </fieldset>

      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Change password</legend>
          {error && <p className="error">{error}</p>}
          {success && <p className="success">{success}</p>}
          <label>
            Current password
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          <label>
            New password
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </label>
          <label>
            Confirm new password
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </label>
          <button type="submit" className="primary" disabled={submitting}>
            {submitting ? "Updating…" : "Update password"}
          </button>
        </fieldset>
      </form>

      <button className="link-button" onClick={logout}>
        Sign out
      </button>
    </main>
  );
}
