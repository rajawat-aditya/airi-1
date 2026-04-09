"use client"
import { useState } from "react";
import { Button } from "@fluentui/react-components";
import { NotepadPerson24Filled, Edit24Regular, Delete24Regular } from "@fluentui/react-icons";
import EditMemoryModal from "./EditMemoryModal";

function MemoryCard({ memory, onDelete, onUpdate }) {
    const [showEdit, setShowEdit] = useState(false);
    const [editText, setEditText] = useState(memory?.memory || "");
    const [saving, setSaving] = useState(false);

    const text = memory?.memory || "";
    const createdAt = memory?.created_at
        ? new Date(memory.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
        : null;

    const handleSave = async () => {
        if (!editText.trim()) return;
        setSaving(true);
        await onUpdate(memory.id, editText.trim());
        setSaving(false);
        setShowEdit(false);
    };

    return (
        <>
            <div className="rounded-xl bg-bg-modal border border-border-default p-4 flex flex-col gap-3 min-h-[160px] hover:shadow-lg transition-shadow duration-200 group">
                <div className="flex justify-between items-start">
                    <NotepadPerson24Filled style={{ fontSize: 20, color: 'var(--accent-blue)' }} />
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button
                            appearance="subtle"
                            size="small"
                            icon={<Edit24Regular />}
                            onClick={() => { setEditText(text); setShowEdit(true); }}
                            aria-label="Edit memory"
                        />
                        <Button
                            appearance="subtle"
                            size="small"
                            icon={<Delete24Regular style={{ color: 'var(--accent-red)' }} />}
                            onClick={() => onDelete(memory.id)}
                            aria-label="Delete memory"
                        />
                    </div>
                </div>
                <p className="text-sm text-text-primary leading-relaxed line-clamp-6 flex-1">{text}</p>
                {createdAt && <span className="text-[11px] text-text-muted mt-auto">{createdAt}</span>}
            </div>
            {showEdit && (
                <EditMemoryModal
                    editDescription={editText}
                    setEditDescription={setEditText}
                    handleSaveEdit={handleSave}
                    setShowEditModal={setShowEdit}
                    saving={saving}
                />
            )}
        </>
    );
}

export default MemoryCard;
