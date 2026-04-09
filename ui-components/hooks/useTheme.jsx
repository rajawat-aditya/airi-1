"use client";
import { createContext, useContext, useEffect, useState } from "react";

const AGENT_URL = "http://127.0.0.1:11435";

const ThemeContext = createContext();

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    if (typeof window === "undefined") return "Night";
    const saved = localStorage.getItem("theme");
    if (saved) return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "Night" : "Day";
  });

  // Apply dark class + save to localStorage + persist to settings.json
  const setTheme = (newTheme) => {
    setThemeState(newTheme);
    // Persist to agent settings.json in background
    fetch(`${AGENT_URL}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: newTheme }),
    }).catch(() => {}); // silent — settings.json is best-effort
  };

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "Night") root.classList.add("dark");
    else root.classList.remove("dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  // On mount, sync from settings.json if localStorage has no saved theme
  useEffect(() => {
    if (localStorage.getItem("theme")) return; // already have a local preference
    fetch(`${AGENT_URL}/settings`)
      .then((r) => r.json())
      .then((s) => {
        if (s.theme === "Day" || s.theme === "Night") {
          setThemeState(s.theme);
          localStorage.setItem("theme", s.theme);
        }
      })
      .catch(() => {});
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
