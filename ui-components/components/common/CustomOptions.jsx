import { ChevronDown24Regular } from "@fluentui/react-icons";
import { useEffect, useRef, useState } from "react";

function CustomOptions({ label, options, value, onChange, error }) {
  const [open, setOpen] = useState(false);
  const elemRef = useRef();

  useEffect(() => {
    function handleClickOutside(event) {
      if (elemRef.current && !elemRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative w-full" ref={elemRef}>
      {label && (
        <span className="block text-sm font-medium text-text-primary mb-2">
          {label} {error && <span style={{ color: 'var(--accent-red)' }}>*</span>}
        </span>
      )}

      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between bg-bg-card border rounded-xl pl-4 pr-3 py-3 text-sm transition-colors text-text-primary hover:bg-bg-hover"
        style={{ borderColor: error ? 'var(--accent-red)' : 'var(--border-default)' }}
      >
        <span className={value ? 'text-text-primary' : 'text-text-muted'}>{value || "Select…"}</span>
        <ChevronDown24Regular style={{
          fontSize: 16,
          color: 'var(--text-muted)',
          transform: open ? 'rotate(180deg)' : 'none',
          transition: 'transform 150ms',
        }} />
      </button>

      {open && (
        <ul className="absolute mt-1 w-full bg-bg-modal border border-border-default rounded-xl shadow-lg z-20 max-h-48 overflow-y-auto lean-slider">
          {options.map((opt) => (
            <li
              key={opt}
              onClick={() => { onChange(opt); setOpen(false); }}
              className={`px-4 py-2.5 text-sm cursor-pointer transition-colors ${
                value === opt ? "bg-bg-hover text-text-primary font-medium" : "text-text-muted hover:bg-bg-hover"
              }`}
            >
              {opt}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default CustomOptions;
