import { ChevronRight24Regular } from "@fluentui/react-icons";

function AppItem({ icon, title, description }) {
    return (
        <div className="w-full flex items-center justify-between p-4 rounded-xl bg-bg-card hover:bg-bg-hover transition-colors cursor-pointer border border-border-default">
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg overflow-hidden flex items-center justify-center bg-bg-modal border border-border-default">
                    <img src={icon} alt={title} className="w-7 h-7 object-contain" />
                </div>
                <div>
                    <h3 className="font-medium text-text-primary text-sm">{title}</h3>
                    <p className="text-xs text-text-muted mt-0.5">{description}</p>
                </div>
            </div>
            <ChevronRight24Regular style={{ fontSize: 16, color: 'var(--text-muted)' }} />
        </div>
    );
}

export default AppItem;
