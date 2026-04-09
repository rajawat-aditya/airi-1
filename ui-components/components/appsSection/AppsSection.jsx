import { TabList, Tab } from "@fluentui/react-components";
import { Grid24Filled } from "@fluentui/react-icons";
import AppItem from "./AppItem";
import { useMemo, useState } from "react";

function AppsSection({ appsList, onSelect }) {
    const [selectedCategory, setSelectedCategory] = useState("Featured");

    const categories = useMemo(() => {
        const unique = [...new Set(appsList.map((app) => app.category))];
        return ["Featured", ...unique];
    }, [appsList]);

    const filteredApps = useMemo(() => {
        if (selectedCategory === "Featured") return appsList;
        return appsList.filter((app) => app.category === selectedCategory);
    }, [selectedCategory, appsList]);

    return (
        <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-4xl mx-auto">
                <div className="flex items-center gap-3 mb-2">
                    <Grid24Filled style={{ fontSize: 28, color: 'var(--accent-blue)' }} />
                    <div>
                        <div className="flex items-center gap-2">
                            <h1 className="text-2xl font-semibold text-text-primary" style={{ fontFamily: 'var(--font-heading)' }}>Apps</h1>
                            <span className="text-xs bg-bg-card border border-border-default px-2 py-0.5 rounded-full text-text-muted">BETA</span>
                        </div>
                        <p className="text-sm text-text-muted">Chat with your favorite apps in Airi</p>
                    </div>
                </div>

                <TabList
                    selectedValue={selectedCategory}
                    onTabSelect={(e, d) => setSelectedCategory(d.value)}
                    style={{ marginBottom: 24, marginTop: 16 }}
                >
                    {categories.map((cat) => (
                        <Tab key={cat} value={cat}>{cat}</Tab>
                    ))}
                </TabList>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {filteredApps.map((app) => (
                        <div onClick={() => onSelect(app)} key={app.name} className="cursor-pointer">
                            <AppItem icon={app.icon} title={app.name} description={app.shortDes} />
                        </div>
                    ))}
                    {filteredApps.length === 0 && (
                        <p className="text-text-muted text-sm col-span-2 text-center py-8">No apps in this category.</p>
                    )}
                </div>
            </div>
        </div>
    );
}

export default AppsSection;
