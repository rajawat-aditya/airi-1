"use client"

import { clsx } from "clsx";
import { useState } from "react";
import { useRouter } from "next/navigation";
import ChatItem from "./chatItem/chatItem";
import { SettingsModal } from "../../ui-components/components/SettingModal";
import { useChatContext } from "@/context/ChatContext";
import LogoMark from "./LogoMark";
import {
    PanelLeft24Regular, PanelLeftContract24Regular,
    AddCircle20Color, Library24Color,
    BrainCircuit24Filled, Person24Filled,
    Settings24Filled, SignOut24Regular,
    AddStarburst24Color,
    SearchSparkle24Color,
    DocumentFolder24Color,
    PersonStarburst24Color,
} from "@fluentui/react-icons";

const AppSideBar = ({ session, profilePicBase64, userId }) => {
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const { chats, removeChat, addOrUpdateChat } = useChatContext();
    const router = useRouter();

    const handleDeleteChat = async (chatId) => {
        if (typeof window === "undefined" || !window.electronAPI) return;
        await window.electronAPI.deleteChat(chatId, userId);
        removeChat(chatId);
    };

    const handleRenameChat = async (chatId, newTitle) => {
        const chat = chats.find((c) => c.chatId === chatId);
        if (!chat) return;
        const updated = { ...chat, chatTitle: newTitle, updatedAt: Date.now() };
        addOrUpdateChat(updated);
        if (typeof window !== "undefined" && window.electronAPI) {
            await window.electronAPI.saveChat(updated);
        }
    };
    return (
        <>
            <div className={clsx("fixed inset-y-0 left-0 z-50 bg-bg-card", "transition-transform duration-300 ease-in-out", "data-[state=close]:-translate-x-full data-[state=open]:translate-x-0", "w-[256px]", "md:relative md:data-[state=close]:translate-x-0 md:transition-all", "md:data-[state=open]:w-[256px] md:data-[state=close]:w-13", "h-screen overflow-hidden group")} data-state="open" id="sidebar">
                <div className="w-full max-w-[256px] px-1 pb-0.5 pt-4 select-none">
                    <div className="flex justify-between items-center group-data-[state=close]:flex-col group-data-[state=close]:gap-2 group-data-[state=close]:items-start">
                        <LogoMark collapsed={sidebarCollapsed} />
                        <div onClick={() => {
                            const sidebar = document.getElementById("sidebar");
                            const newState = sidebar.getAttribute('data-state') === 'open' ? 'close' : 'open';
                            sidebar.setAttribute('data-state', newState);
                            setSidebarCollapsed(newState === 'close');
                        }} className="text-[14px] outline-offset-1 flex items-center justify-center hover:bg-bg-hover transition-all duration-100 cursor-pointer bg-transparent text-text-muted font-medium w-9 h-9 rounded-lg">
                            {sidebarCollapsed ? <PanelLeft24Regular /> : <PanelLeftContract24Regular />}
                        </div>
                    </div>
                    <div className="flex flex-col gap-1 pt-1 items-center group-data-[state=close]:items-start">
                        <button onClick={() => router.push(`/app/${crypto.randomUUID()}`)} className="group-data-[state=close]:w-9 group-data-[state=close]:h-9 flex w-full gap-2 h-10 items-center px-2 py-1.5 rounded-xl hover:bg-bg-hover cursor-pointer transition-all duration-100 ease-in-out">
                            <span className="text-accent-blue shrink-0"><AddStarburst24Color style={{ fontSize: 20 }} /></span>
                            <span className="group-data-[state=close]:hidden flex min-h-6 w-full font-medium items-center gap-1.5 text-start text-[14px] text-text-primary">New chat</span>
                        </button>
                        <button onClick={() => router.push('/library')} className="group-data-[state=close]:w-9 group-data-[state=close]:h-9 flex w-full gap-2 h-10 items-center px-2 py-1.5 rounded-xl hover:bg-bg-hover cursor-pointer transition-all duration-100 ease-in-out">
                            <span className="text-accent-blue shrink-0">
                                <DocumentFolder24Color style={{ fontSize: 20 }} />
                            </span>
                            <span className="group-data-[state=close]:hidden flex min-h-6 w-full font-medium items-center gap-1.5 text-start text-[14px] text-text-primary">Library</span>
                        </button>
                        <button onClick={() => router.push('/memory')} className="group-data-[state=close]:w-9 group-data-[state=close]:h-9 flex w-full gap-2 h-10 items-center px-2 py-1.5 rounded-xl hover:bg-bg-hover cursor-pointer transition-all duration-100 ease-in-out">
                            <span className="text-accent-blue shrink-0">
                                <SearchSparkle24Color style={{ fontSize: 20 }} />
                            </span>
                            <span className="group-data-[state=close]:hidden flex min-h-6 w-full font-medium items-center gap-1.5 text-start text-[14px] text-text-primary">Memory</span>
                        </button>
                    </div>
                    <div className="h-6 rounded-xl py-3 w-full px-2 group-data-[state=close]:hidden"><div className="h-0 border-t border-border-default"></div></div>
                    {/* chats */}
                    <div className="group-data-[state=close]:hidden overflow-y-auto max-h-[calc(100vh-280px)]">
                        {!session && (
                            <p className="px-2.5 pb-6 font-medium text-text-muted text-[14px]">Sign in to save our conversations.</p>
                        )}
                        {session && chats.map((chat) => (
                            <ChatItem
                                key={chat.chatId}
                                chat={chat}
                                onClick={() => router.push(`/app/${chat.chatId}`)}
                                onDelete={() => handleDeleteChat(chat.chatId)}
                                onRename={handleRenameChat}
                            />
                        ))}
                        {session && chats.length === 0 && (
                            <p className="px-2.5 pb-6 font-medium text-text-muted text-[14px]">No conversations yet.</p>
                        )}
                    </div>
                    {/* account */}
                    <div className="absolute bottom-2 w-full max-w-[256px]">
                        {!session && (
                            <button onClick={() => window.location.href = "/login"} className="group-data-[state=close]:w-9 group-data-[state=close]:h-9 flex w-full gap-2 h-10 items-center px-1.5 py-1.5 rounded-xl hover:bg-bg-hover cursor-pointer transition-all duration-100 ease-in-out">
                                <span className="text-accent-blue shrink-0">
                                    <Person24Filled style={{ fontSize: 22 }} />
                                </span>
                                <span className="group-data-[state=close]:hidden flex min-h-6 w-full font-medium items-center gap-1.5 text-start text-[14px] text-text-primary">Sign in</span>
                            </button>
                        )}
                        {session && (
                            <div className="relative">
                                <button
                                    popoverTarget="profilemenu"
                                    style={{ anchorName: "--profile-anchor" }}
                                    className="group-data-[state=close]:w-9 group-data-[state=close]:h-9 flex w-full gap-2 h-10 items-center px-1.5 py-1.5 rounded-xl hover:bg-bg-hover cursor-pointer transition-all duration-100 ease-in-out"
                                >
                                    <PersonStarburst24Color style={{ fontSize: 24, flexShrink: 0 }} />
                                    <span className="group-data-[state=close]:hidden flex min-h-6 w-full font-medium items-center gap-1.5 text-start text-[15px] truncate text-text-primary">
                                        {session.user.name}
                                    </span>
                                </button>
                                <div
                                    popover="auto"
                                    id="profilemenu"
                                    style={{ positionAnchor: "--profile-anchor" }}
                                    className="popover-content p-1 bg-bg-modal border border-border-default rounded-xl shadow-2xl text-text-primary min-w-69"
                                >
                                    <button onClick={() => setSettingsOpen(true)} className="font-medium cursor-pointer flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[14px] hover:bg-bg-hover transition-all duration-100">
                                        <Settings24Filled style={{ fontSize: 16, color: 'var(--accent-blue)' }} /> Settings
                                    </button>
                                    <button onClick={() => window.location.href = "/auth/logout"} className="font-medium cursor-pointer flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[14px] hover:bg-bg-hover transition-all duration-100">
                                        <SignOut24Regular style={{ fontSize: 16 }} /> Sign out
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
            <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} name={session?.user?.name} email={session?.user?.email} />
        </>
    )
}

export default AppSideBar;
