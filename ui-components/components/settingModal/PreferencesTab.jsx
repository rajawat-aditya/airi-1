import { ChevronDown24Regular } from "@fluentui/react-icons";
import { ThemeToggler } from "./ThemeToggler";
import { useState, useEffect } from "react";
import { VoiceLanguageDropdown } from "./VoiceLanguageDropdown";
import { useTheme } from "../../hooks/useTheme";

const AGENT_URL = "http://127.0.0.1:11435";

function SettingDropdown({ value, setValue, options }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative w-40">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between bg-bg-hover border border-border-default rounded-lg pl-4 pr-3 py-2 text-sm focus:outline-none focus:border-border-active transition-colors"
      >
        {value}
        <ChevronDown24Regular style={{ fontSize: 16, color: 'var(--text-muted)', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms' }} />
      </button>
      {open && (
        <ul className="absolute mt-2 w-full bg-bg-card border border-border-default rounded-lg shadow-lg z-10 max-h-80 overflow-y-auto lean-slider">
          {options.map((opt) => (
            <li
              key={opt}
              onClick={() => { setValue(opt); setOpen(false); }}
              className={`px-4 py-2 text-sm cursor-pointer hover:bg-bg-hover ${value === opt ? "bg-bg-hover text-text-primary" : "text-text-muted"}`}
            >
              {opt}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FieldInput({ label, value, onChange, placeholder, type = "text" }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-text-muted">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-bg-hover border border-border-default rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-border-active transition-colors placeholder:text-text-muted"
      />
    </div>
  );
}

export function PreferencesTab() {
  const { theme, setTheme } = useTheme();
  const [voiceLan, setVoiceLan] = useState("Auto-detect");
  const [voice, setVoice] = useState("Wave");
  const [language, setLanguage] = useState("EN");

  // Model source
  const [modelSource, setModelSource] = useState("local"); // "local" | "api"
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiModel, setApiModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // "ok" | "err"

  useEffect(() => {
    fetch(`${AGENT_URL}/settings`)
      .then((r) => r.json())
      .then((s) => {
        const isLocal =
          !s.model_server ||
          s.model_server.includes("127.0.0.1") ||
          s.model_server.includes("localhost");
        setModelSource(isLocal ? "local" : "api");
        setApiBase(isLocal ? "" : (s.model_server ?? ""));
        setApiKey(s.api_key && s.api_key !== "none" ? s.api_key : "");
        setApiModel(s.model && s.model !== "default" ? s.model : "");
      })
      .catch(() => {});
  }, []);

  async function saveInferenceSettings() {
    setSaving(true);
    setSaveStatus(null);
    try {
      const payload =
        modelSource === "local"
          ? { model_server: "http://127.0.0.1:11434/v1", model: "default", api_key: "none" }
          : { model_server: apiBase.trim(), model: apiModel.trim() || "default", api_key: apiKey.trim() || "none" };

      const res = await fetch(`${AGENT_URL}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setSaveStatus(res.ok ? "ok" : "err");
    } catch {
      setSaveStatus("err");
    } finally {
      setSaving(false);
      setTimeout(() => setSaveStatus(null), 3000);
    }
  }

  return (
    <div className="max-w-2xl">
      <h3 className="text-lg font-semibold mb-6">Preferences</h3>

      {/* Model Source */}
      <div className="bg-bg-card rounded-xl border border-border-default mb-4">
        <div className="p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Model source</p>
              <p className="text-xs text-text-muted mt-0.5">Run locally or use an OpenAI-compatible inference API</p>
            </div>
            <div className="flex gap-2">
              {["local", "api"].map((src) => (
                <button
                  key={src}
                  onClick={() => setModelSource(src)}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                    modelSource === src
                      ? "bg-bg-hover text-text-primary border border-border-active"
                      : "text-text-muted hover:bg-bg-hover/50 border border-transparent"
                  }`}
                >
                  {src === "local" ? "Local" : "Inference API"}
                </button>
              ))}
            </div>
          </div>

          {modelSource === "api" && (
            <div className="flex flex-col gap-4 pt-1 border-t border-border-default">
              <FieldInput
                label="API Base URL"
                value={apiBase}
                onChange={setApiBase}
                placeholder="https://api.openai.com/v1"
              />
              <FieldInput
                label="API Key"
                value={apiKey}
                onChange={setApiKey}
                placeholder="sk-..."
                type="password"
              />
              <FieldInput
                label="Model"
                value={apiModel}
                onChange={setApiModel}
                placeholder="gpt-4o"
              />
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={saveInferenceSettings}
              disabled={saving}
              className="px-4 py-1.5 rounded-lg text-sm font-medium bg-bg-hover border border-border-default hover:border-border-active transition-colors cursor-pointer disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            {saveStatus === "ok" && <span className="text-xs text-green-400">Saved</span>}
            {saveStatus === "err" && <span className="text-xs text-red-400">Failed to save</span>}
          </div>
        </div>
      </div>

      {/* Other preferences */}
      <div className="bg-bg-card rounded-xl border border-border-default">
        <div className="p-6 flex flex-col gap-6">
          <VoiceLanguageDropdown value={voiceLan} setValue={setVoiceLan} />
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Voice</span>
            <SettingDropdown value={voice} setValue={setVoice} options={["Wave", "Echo"]} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Language</span>
            <SettingDropdown value={language} setValue={setLanguage} options={["EN", "ES"]} />
          </div>
          <ThemeToggler theme={theme} setTheme={setTheme} />
        </div>
      </div>
    </div>
  );
}
