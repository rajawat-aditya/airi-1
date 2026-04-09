"use client"
import { Dialog, DialogSurface, DialogTitle, DialogBody, DialogContent, DialogActions, Button, Textarea } from "@fluentui/react-components";
import { Dismiss24Regular } from "@fluentui/react-icons";

function EditMemoryModal({ editDescription, setEditDescription, setShowEditModal, handleSaveEdit, saving }) {
    return (
        <Dialog open onOpenChange={(e, d) => { if (!d.open) setShowEditModal(false); }}>
            <DialogSurface style={{ maxWidth: 480 }}>
                <DialogBody>
                    <DialogTitle action={
                        <Button appearance="subtle" icon={<Dismiss24Regular />} onClick={() => setShowEditModal(false)} aria-label="Close" />
                    }>
                        Edit Memory
                    </DialogTitle>
                    <DialogContent>
                        <Textarea
                            value={editDescription}
                            onChange={(e) => setEditDescription(e.target.value)}
                            placeholder="Memory content"
                            rows={6}
                            style={{ width: '100%' }}
                            autoFocus
                        />
                    </DialogContent>
                    <DialogActions>
                        <Button appearance="secondary" onClick={() => setShowEditModal(false)}>Cancel</Button>
                        <Button appearance="primary" onClick={handleSaveEdit} disabled={saving}>
                            {saving ? "Saving…" : "Save"}
                        </Button>
                    </DialogActions>
                </DialogBody>
            </DialogSurface>
        </Dialog>
    );
}

export default EditMemoryModal;
