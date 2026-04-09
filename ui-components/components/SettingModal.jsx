import { useState } from "react";
import { Dismiss24Regular } from "@fluentui/react-icons";
import { Dialog, DialogSurface, DialogBody, DialogContent, TabList, Tab, Button } from "@fluentui/react-components";
import { AccountTab } from "./settingModal/AccountTab";
import { AboutTab } from "./settingModal/AboutTab";
import { PreferencesTab } from "./settingModal/PreferencesTab";
import "../index.css";

export function SettingsModal({ onClose, name, email, open = true }) {
  const [activeTab, setActiveTab] = useState("Preferences");

  return (
    <Dialog open={open} onOpenChange={(e, data) => { if (!data.open) onClose(); }}>
      <DialogSurface style={{ maxWidth: '56rem', width: '100%', padding: 0, borderRadius: 'var(--borderRadiusXLarge)' }}>
        <DialogBody style={{ display: 'flex', flexDirection: 'column', minHeight: '540px' }}>
          {/* Custom header: title left, close button right */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 16px 8px 24px' }}>
            <span style={{ fontFamily: 'var(--font-heading)', fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>
              Settings
            </span>
            <Button
              appearance="subtle"
              icon={<Dismiss24Regular />}
              onClick={onClose}
              aria-label="Close settings"
            />
          </div>
          <DialogContent className="settings-body">
            {/* Tab sidebar */}
            <div className="settings-tabs" style={{ minWidth: 140, padding: '8px 8px 8px 16px' }}>
              <TabList
                vertical
                selectedValue={activeTab}
                onTabSelect={(_, data) => setActiveTab(data.value)}
                style={{ gap: 2 }}
              >
                <Tab value="Preferences">Preferences</Tab>
                <Tab value="Account">Account</Tab>
                <Tab value="About">About</Tab>
              </TabList>
            </div>
            {/* Content area */}
            <div className="settings-content" style={{ flex: 1, padding: '8px 24px 8px 16px', overflowY: 'auto', background: 'var(--bg-app)', borderRadius: 8 }}>
              {activeTab === "Account" && <AccountTab email={email} name={name} />}
              {activeTab === "About" && <AboutTab />}
              {activeTab === "Preferences" && <PreferencesTab />}
            </div>
          </DialogContent>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
