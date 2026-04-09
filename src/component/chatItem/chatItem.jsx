"use client"
import { useState, useRef, useEffect } from "react";
import { MoreHorizontal20Regular, Rename20Regular, Share20Regular, Delete20Regular, Checkmark20Regular, Dismiss20Regular } from "@fluentui/react-icons";

function safeCopy(text) {
    try {
        const el = document.createElement('textarea');
        el.value = text;
        el.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0';
        document.body.appendChild(el);
        el.focus();
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
    } catch (e) {
        console.warn('[copy] execCommand failed:', e);
    }
}

export default function ChatItem({ chat, onClick, onDelete, onRename }) {
    const popoverId = `chat-options-${chat.chatId}`;
    const anchorName = `--anchor-${chat.chatId}`;
    const [renaming, setRenaming] = useState(false);
    const [renameValue, setRenameValue] = useState(chat.chatTitle);
    const inputRef = useRef(null);

    useEffect(() => {
        if (renaming) inputRef.current?.focus();
    }, [renaming]);

    const commitRename = (e) => {
        e?.stopPropagation();
        const trimmed = renameValue.trim();
        if (trimmed && trimmed !== chat.chatTitle) {
            onRename?.(chat.chatId, trimmed);
        }
        setRenaming(false);
    };

    const cancelRename = (e) => {
        e?.stopPropagation();
        setRenameValue(chat.chatTitle);
        setRenaming(false);
    };

    if (renaming) {
        return (
            <div
                className="flex size-full items-center gap-1 px-1 py-0.5"
                onClick={(e) => e.stopPropagation()}
            >
                <input
                    ref={inputRef}
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') commitRename();
                        if (e.key === 'Escape') cancelRename();
                    }}
                    className="flex-1 min-w-0 bg-bg-hover border border-border-active rounded-lg px-2 py-1 text-[13px] text-text-primary outline-none"
                />
                <button
                    onClick={commitRename}
                    className="flex items-center justify-center size-6 rounded-lg hover:bg-bg-hover text-accent-blue transition-colors cursor-pointer"
                    aria-label="Confirm rename"
                >
                    <Checkmark20Regular style={{ fontSize: 14 }} />
                </button>
                <button
                    onClick={cancelRename}
                    className="flex items-center justify-center size-6 rounded-lg hover:bg-bg-hover text-text-muted transition-colors cursor-pointer"
                    aria-label="Cancel rename"
                >
                    <Dismiss20Regular style={{ fontSize: 14 }} />
                </button>
            </div>
        );
    }

    return (
        <div
            onClick={onClick}
            className="flex size-full items-center justify-between pb-1.5 rounded-2xl hover:bg-bg-hover px-0.5 py-0.5 cursor-pointer transition-all duration-100 group/item"
        >
            <div className="flex h-full min-w-0 flex-1 items-center gap-1.5 px-2.5 font-medium text-text-muted text-[14px]">
                <p className="truncate text-text-muted" title={chat.chatTitle}>
                    {chat.chatTitle}
                </p>
            </div>

            <button
                popoverTarget={popoverId}
                style={{ anchorName: anchorName }}
                aria-label="View Options"
                type="button"
                onClick={(e) => e.stopPropagation()}
                className="relative flex items-center justify-center text-xs outline-offset-1 rounded-lg size-6 opacity-0 group-hover/item:opacity-100 hover:bg-bg-hover transition-all duration-100 text-text-muted"
            >
                <MoreHorizontal20Regular />
            </button>

            <div
                popover="auto"
                id={popoverId}
                style={{ positionAnchor: anchorName }}
                onClick={(e) => e.stopPropagation()}
                className="chat-options-menu bg-bg-modal border border-border-default rounded-xl shadow-2xl p-1 min-w-37.5"
            >
                <button
                    onClick={(e) => { e.stopPropagation(); setRenameValue(chat.chatTitle); setRenaming(true); document.getElementById(popoverId)?.hidePopover?.(); }}
                    className="cursor-pointer flex w-full font-medium items-center gap-2 rounded-lg px-3 py-2 text-[14px] text-text-primary hover:bg-bg-hover transition-all"
                >
                    <Rename20Regular style={{ fontSize: 16, color: 'var(--accent-blue)' }} />
                    Rename
                </button>
                <button
                    onClick={onDelete}
                    className="cursor-pointer flex w-full font-medium items-center gap-2 rounded-lg px-3 py-2 text-[14px] text-accent-red hover:bg-accent-red/10 transition-all"
                >
                    <Delete20Regular style={{ fontSize: 16 }} />
                    Delete
                </button>
            </div>
        </div>
    );
}
