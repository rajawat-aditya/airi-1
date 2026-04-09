import { ChevronDown24Regular } from "@fluentui/react-icons";
import { useState } from "react";

export function VoiceLanguageDropdown({ value, setValue }) {
    const [open, setOpen] = useState(false);
    const options = ["Auto-Detect", "English"];

    return (
        <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-text-primary">Voice language</span>
            <div className="relative w-40">
                <button
                    onClick={() => setOpen(!open)}
                    className="w-full flex items-center justify-between bg-bg-hover border border-border-default rounded-lg pl-4 pr-3 py-2 text-sm focus:outline-none focus:border-border-active transition-colors text-text-primary"
                >
                    {value}
                    <ChevronDown24Regular style={{ fontSize: 16, color: 'var(--text-muted)', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms' }} />
                </button>
                {open && (
                    <ul className="absolute mt-1 w-full bg-bg-modal border border-border-default rounded-lg shadow-lg z-10 overflow-hidden">
                        {options.map((opt) => (
                            <li
                                key={opt}
                                onClick={() => { setValue(opt); setOpen(false); }}
                                className={`px-4 py-2 text-sm cursor-pointer hover:bg-bg-hover transition-colors ${value === opt ? "text-text-primary bg-bg-hover" : "text-text-muted"}`}
                            >
                                {opt}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
