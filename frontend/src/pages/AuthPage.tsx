import { FormEvent, useState } from "react";

import { ApiError, api } from "../api";

interface Props {
  onAuthed: (token: string) => void;
}

export default function AuthPage({ onAuthed }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const call = mode === "login" ? api.login : api.register;
      const { access_token } = await call(email.trim(), password);
      onAuthed(access_token);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "出了点问题，请再试一次");
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";

  return (
    <main className="page auth">
      <section className="specimen" aria-label="WordPath">
        <p className="specimen-word">vocabulary</p>
        <p className="specimen-phonetic">/vəˈkæbjəˌlɛri/</p>
        <p className="specimen-meaning">n. 词汇；词汇量</p>
        <p className="specimen-note">
          每天学一点，按遗忘规律复习。忘得快的词多见几次，记住的词慢慢拉长间隔。
        </p>
      </section>

      <form className="auth-form" onSubmit={submit}>
        <h1>{isLogin ? "登录" : "注册"}</h1>
        <label>
          邮箱
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          密码
          <input
            type="password"
            autoComplete={isLogin ? "current-password" : "new-password"}
            required
            minLength={isLogin ? undefined : 8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {!isLogin && <p className="hint">至少 8 个字符</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button className="primary" type="submit" disabled={busy}>
          {busy ? "请稍候…" : isLogin ? "登录" : "注册并开始"}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(isLogin ? "register" : "login");
            setError(null);
          }}
        >
          {isLogin ? "还没有账号？注册" : "已经有账号？登录"}
        </button>
      </form>
    </main>
  );
}
