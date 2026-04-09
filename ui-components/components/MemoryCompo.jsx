"use client"
import { useState, useEffect, useCallback } from "react";
import { Spinner } from "@fluentui/react-components";
import { BrainCircuit24Filled } from "@fluentui/react-icons";
import MemoryCard from "./memoryCompo/MemoryCard";
import InitialMemorySec from "./memoryCompo/InitialMemorySec";

const AGENT_URL = "http://127.0.0.1:11435";

function MemoryCompo({ userId = "default_user" }) {
    const [memories, setMemories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchMemories = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${AGENT_URL}/memories?user_id=${encodeURIComponent(userId)}`);
            const data = await res.json();
            setMemories(data.memories || []);
        } catch {
            setError("Could not connect to agent server.");
        } finally {
            setLoading(false);
        }
    }, [userId]);

    useEffect(() => { fetchMemories(); }, [fetchMemories]);

    const handleDelete = useCallback(async (memoryId) => {
        try {
            await fetch(`${AGENT_URL}/memories/${memoryId}`, { method: "DELETE" });
            setMemories((prev) => prev.filter((m) => m.id !== memoryId));
        } catch (e) { console.error("[memory] delete error:", e); }
    }, []);

    const handleUpdate = useCallback(async (memoryId, newText) => {
        try {
            await fetch(`${AGENT_URL}/memories/${memoryId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ data: newText }),
            });
            setMemories((prev) => prev.map((m) => m.id === memoryId ? { ...m, memory: newText } : m));
        } catch (e) { console.error("[memory] update error:", e); }
    }, []);

    if (loading) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <Spinner size="medium" label="Loading memories…" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <p className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</p>
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto p-6">
            {memories.length === 0 ? (
                <div className="relative flex flex-col items-center justify-center min-h-[60vh]">
                    <InitialMemorySec />
                </div>
            ) : (
                <div className="max-w-7xl mx-auto">
                    <div className="flex items-center gap-3 mb-6">
                        <BrainCircuit24Filled style={{ fontSize: 28, color: 'var(--accent-blue)' }} />
                        <h1 className="text-2xl font-semibold text-text-primary" style={{ fontFamily: 'var(--font-heading)' }}>Memory</h1>
                        <span className="text-xs text-text-muted bg-bg-hover border border-border-default px-2 py-0.5 rounded-full">{memories.length}</span>
                    </div>
                    <div className="grid grid-cols-4 max-lg:grid-cols-3 max-md:grid-cols-2 max-sm:grid-cols-1 gap-4">
                        {memories.map((memory) => (
                            <MemoryCard key={memory.id} memory={memory} onDelete={handleDelete} onUpdate={handleUpdate} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

export default MemoryCompo;
