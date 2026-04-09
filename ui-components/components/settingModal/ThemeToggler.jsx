import { WeatherSunny24Filled, WeatherMoon24Filled } from "@fluentui/react-icons";

export function ThemeToggler({ theme, setTheme }) {
    return (
        <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-text-primary">Theme</span>
            <div className="flex rounded-lg border border-border-default overflow-hidden">
                <button
                    onClick={() => setTheme("Day")}
                    className={`flex items-center gap-2 px-4 py-2 text-sm transition-colors cursor-pointer ${
                        theme === "Day" ? "bg-bg-hover text-text-primary" : "bg-bg-card text-text-muted"
                    }`}
                >
                    <WeatherSunny24Filled style={{ fontSize: 16, color: theme === "Day" ? '#f59e0b' : 'var(--text-muted)' }} />
                    Day
                </button>
                <button
                    onClick={() => setTheme("Night")}
                    className={`flex items-center gap-2 px-4 py-2 text-sm transition-colors cursor-pointer ${
                        theme === "Night" ? "bg-bg-hover text-text-primary" : "bg-bg-card text-text-muted"
                    }`}
                >
                    <WeatherMoon24Filled style={{ fontSize: 16, color: theme === "Night" ? '#818cf8' : 'var(--text-muted)' }} />
                    Night
                </button>
            </div>
        </div>
    );
}
