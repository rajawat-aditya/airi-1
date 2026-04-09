"use client";
import { Spinner } from "@fluentui/react-components";

export const TOOL_LABELS = {
    browser_automation:     "Browsing the web",
    search_win_app_by_name: "Searching for app",
    start_app_session:      "Launching app",
    inspect_ui_elements:    "Inspecting UI elements",
    list_element_names:     "Reading interface",
    get_element_details:    "Locating element",
    stop_app_session:       "Closing app session",
    manage_memory:          "Accessing memory",
    web_search:             "Searching the web",
};

export default function AgentLoader({ toolName }) {
    const label = toolName
        ? (TOOL_LABELS[toolName] ?? toolName.replace(/_/g, " "))
        : "Thinking";

    return (
        <div
            className="flex items-center gap-3 px-4 py-3 max-w-fit rounded-2xl rounded-tl-sm border border-border-default shadow-md mt-1 bg-bg-card"
        >
            <div className="flex items-center gap-2 shrink-0">
                <Spinner size="tiny" />
                <img src="/logo.png" alt="Airi" style={{ width: 18, height: 18, objectFit: 'contain', borderRadius: 4 }} />
            </div>
            <span
                className="text-text-muted min-w-[120px]"
                style={{ fontFamily: "var(--font-body)", fontSize: 14 }}
            >
                {label}…
            </span>
        </div>
    );
}
