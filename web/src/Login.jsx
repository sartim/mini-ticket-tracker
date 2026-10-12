import { useState } from "react";
import { api, setAccessToken } from "./api";

export default function Login({ onAuthenticated }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function signIn(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const tokens = await api("/auth/token", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setAccessToken(tokens.access);
      setPassword("");
      onAuthenticated(tokens.user);
    } catch (requestError) {
      setError(requestError.message === "No active account found with the given credentials"
        ? "The username or password is incorrect."
        : requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-card" aria-label="Sign in">
        <form className="login-form" onSubmit={signIn}>
          <label htmlFor="login-username">Username</label>
          <input id="login-username" autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Enter your username" />
          <label htmlFor="login-password">Password</label>
          <input id="login-password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" />
          {error && <p className="login-error" role="alert">{error}</p>}
          <button className="login-submit" type="submit" disabled={submitting}>{submitting ? "Signing in…" : "Sign in"}</button>
        </form>
        <p className="login-footnote">Use the account provided by your administrator.</p>
      </section>
    </main>
  );
}
