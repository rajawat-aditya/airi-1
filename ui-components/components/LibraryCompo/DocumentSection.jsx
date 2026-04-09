'use client'
import { useState } from "react";
import {
    Code24Regular,
    DocumentPdf24Regular,
    TextDescription24Regular,
    Delete24Regular,
    Document24Regular,
    TableSimple24Regular,
    DataHistogram24Regular,
} from "@fluentui/react-icons";

function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(ts) {
    return new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getIcon(ext) {
    switch (ext) {
        case "pdf":  return <DocumentPdf24Regular />;
        case "js": case "ts": case "jsx": case "tsx":
        case "py": case "html": case "css": case "json": return <Code24Regular />;
        case "csv": case "xlsx": case "xls": return <TableSimple24Regular />;
        case "pptx": return <DataHistogram24Regular />;
        case "doc": case "docx": case "txt": case "md": return <TextDescription24Regular />;
        default: return <Document24Regular />;
    }
}

const DocumentItem = ({ doc, onDelete }) => {
    const [deleting, setDeleting] = useState(false);

    const handleDelete = async (e) => {
        e.stopPropagation();
        setDeleting(true);
        await onDelete(doc.name);
    };

    return (
        <div className="flex items-center gap-4 px-4 py-3 rounded-xl hover:bg-bg-hover transition-colors group">
            <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-bg-hover flex items-center justify-center" style={{ color: 'var(--accent-blue)' }}>
                {getIcon(doc.ext)}
            </div>
            <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-text-primary truncate">{doc.name}</div>
                <div className="text-xs text-text-muted mt-0.5">{formatSize(doc.size)}</div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs text-text-muted">{formatDate(doc.modified)}</span>
                <button
                    onClick={handleDelete}
                    disabled={deleting}
                    title="Delete file"
                    className="cursor-pointer opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-text-muted hover:text-red-400 hover:bg-red-400/10 transition-all"
                >
                    <Delete24Regular />
                </button>
            </div>
        </div>
    );
};

const DocumentSection = ({ documents, onDelete }) => (
    <div className="mb-6">
        <div className="px-4 mb-1">
            <span className="text-sm font-medium text-text-primary">Documents ({documents.length})</span>
        </div>
        <div className="flex flex-col">
            {documents.map((doc) => (
                <DocumentItem key={doc.name} doc={doc} onDelete={onDelete} />
            ))}
        </div>
    </div>
);

export default DocumentSection;
