'use client'
import { useState, useEffect, useCallback } from "react";
import { Spinner } from "@fluentui/react-components";
import { BookmarkMultiple24Filled } from "@fluentui/react-icons";
import DocumentSection from "./LibraryCompo/DocumentSection";
import MediaSection from "./LibraryCompo/MediaSection";

const AGENT_URL = "http://127.0.0.1:11435";

const LibraryCompo = () => {
    const [documents, setDocuments] = useState([]);
    const [media, setMedia] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchFiles = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${AGENT_URL}/library`);
            const data = await res.json();
            setDocuments(data.documents || []);
            setMedia(data.media || []);
        } catch {
            setError("Could not connect to agent server.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchFiles(); }, [fetchFiles]);

    const handleDelete = useCallback(async (filename) => {
        try {
            await fetch(`${AGENT_URL}/library/${encodeURIComponent(filename)}`, { method: "DELETE" });
            setDocuments((prev) => prev.filter((d) => d.name !== filename));
            setMedia((prev) => prev.filter((m) => m.name !== filename));
        } catch (e) { console.error("[library] delete error:", e); }
    }, []);

    return (
        <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-5xl mx-auto">
                <div className="flex items-center gap-3 mb-6">
                    <BookmarkMultiple24Filled style={{ fontSize: 28, color: 'var(--accent-blue)' }} />
                    <h1 className="text-2xl font-semibold text-text-primary" style={{ fontFamily: 'var(--font-heading)' }}>Library</h1>
                </div>

                {loading && (
                    <div className="flex items-center justify-center py-16">
                        <Spinner size="medium" label="Loading files…" />
                    </div>
                )}

                {error && <p className="text-sm py-4" style={{ color: 'var(--accent-red)' }}>{error}</p>}

                {!loading && !error && documents.length === 0 && media.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <BookmarkMultiple24Filled style={{ fontSize: 48, color: 'var(--border-default)', marginBottom: 12 }} />
                        <p className="text-text-muted text-sm">No files yet. Upload documents or images to Airi and they'll appear here.</p>
                    </div>
                )}

                {!loading && !error && (
                    <>
                        {documents.length > 0 && <DocumentSection documents={documents} onDelete={handleDelete} />}
                        {media.length > 0 && <MediaSection media={media} agentUrl={AGENT_URL} onDelete={handleDelete} />}
                    </>
                )}
            </div>
        </div>
    );
};

export default LibraryCompo;
