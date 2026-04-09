import { Button } from "@fluentui/react-components";
import { ArrowLeft24Regular, Globe24Regular, ShieldLock24Regular } from "@fluentui/react-icons";
import InfoRow from "./InfoRow";

function AppDetailCompo({ app, onBack }) {
    return (
        <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-4xl mx-auto">
                <Button
                    appearance="subtle"
                    icon={<ArrowLeft24Regular />}
                    onClick={onBack}
                    style={{ marginBottom: 24 }}
                >
                    Apps
                </Button>

                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-4">
                        <div className="w-16 h-16 rounded-xl overflow-hidden flex items-center justify-center bg-bg-card border border-border-default">
                            <img src={app.icon} alt={app.name} className="w-12 h-12 object-contain" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-semibold text-text-primary" style={{ fontFamily: 'var(--font-heading)' }}>{app.name}</h1>
                            <p className="text-sm text-text-muted mt-1">{app.shortDes}</p>
                        </div>
                    </div>
                    <Button appearance="primary">Connect</Button>
                </div>

                <p className="text-sm text-text-muted leading-relaxed mb-8">{app.longDes}</p>

                <h2 className="text-base font-semibold text-text-primary mb-4">Information</h2>
                <div className="rounded-xl border border-border-default overflow-hidden max-w-xl">
                    <table className="w-full text-sm table-auto border-collapse">
                        <tbody>
                            <InfoRow label="Category" value={app.category} />
                            <InfoRow label="Capabilities" value={app.capabilities.join(", ")} />
                            <InfoRow label="Developer" value={app.developer} />
                            <InfoRow label="Website" value={
                                <a href={app.websitelink} target="_blank" rel="noreferrer">
                                    <Globe24Regular style={{ fontSize: 18, color: 'var(--accent-blue)' }} />
                                </a>
                            } />
                            <InfoRow label="Version" value={app.version} />
                            <InfoRow label="Privacy" value={
                                <a href={app.privacyPolicy} target="_blank" rel="noreferrer">
                                    <ShieldLock24Regular style={{ fontSize: 18, color: 'var(--accent-blue)' }} />
                                </a>
                            } last />
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

export default AppDetailCompo;
