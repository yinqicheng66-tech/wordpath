import { useEffect, useState } from "react";

import { LOGOUT_EVENT, getToken, setToken } from "./api";
import AuthPage from "./pages/AuthPage";
import HomePage from "./pages/HomePage";
import StudyPage from "./pages/StudyPage";
import type { StudyMode } from "./types";

type View = { name: "home" } | { name: "study"; mode: StudyMode };

export default function App() {
  const [token, setTokenState] = useState<string | null>(getToken);
  const [view, setView] = useState<View>({ name: "home" });

  useEffect(() => {
    const onLogout = () => setTokenState(null);
    window.addEventListener(LOGOUT_EVENT, onLogout);
    return () => window.removeEventListener(LOGOUT_EVENT, onLogout);
  }, []);

  if (!token) {
    return (
      <AuthPage
        onAuthed={(t) => {
          setToken(t);
          setTokenState(t);
          setView({ name: "home" });
        }}
      />
    );
  }

  if (view.name === "study") {
    return <StudyPage mode={view.mode} onExit={() => setView({ name: "home" })} />;
  }

  return (
    <HomePage
      onStart={(mode) => setView({ name: "study", mode })}
      onLogout={() => {
        setToken(null);
        setTokenState(null);
      }}
    />
  );
}
