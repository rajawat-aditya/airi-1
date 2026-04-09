"use client"
import ChatInput from "@/component/chatInput/chatInput";
import AgentLoader from "@/component/chatMain/AgentLoader";
import { useCallback, useEffect, useRef, useState } from "react";
import { nanoid } from "nanoid";
import { callAgentAPI } from "@/lib/agent-api";
import { useChatContext } from "@/context/ChatContext";
import { Button } from "@fluentui/react-components";
import { XMarkdown } from "@ant-design/x-markdown";
import {
    ArrowCircleUpRight24Regular,
    Sparkle24Filled,
    ThumbLike24Filled, ThumbDislike24Filled,
    Info16Regular, PanelLeft24Regular, Copy24Regular,
} from "@fluentui/react-icons";

function historyToMessages(chatHistory = []) {
    return chatHistory.map((m, i) => ({
        from: m.role === "user" ? "user" : "assistant",
        key: `history-${i}`,
        versions: [{ content: m.content, id: `history-id-${i}` }],
    }));
}

function messagesToHistory(messages) {
    return messages.map((m) => ({
        role: m.from === "user" ? "user" : "assistant",
        // agentContent stores the full prompt+file-paths string for history replay
        content: m.versions[0].agentContent ?? m.versions[0].content,
    })).filter((m) => m.content);
}

// Safe clipboard copy — works in Electron without clipboard permissions
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

const ChatMain = ({ userId, chatId: initialChatId, user_name }) => {
    const [messages, setMessages] = useState([]);
    const [streamingMessageId, setStreamingMessageId] = useState(null);
    const [activeToolName, setActiveToolName] = useState(null); // current tool being called
    const [feedbackState, setFeedbackState] = useState({}); // { [messageId]: 'up' | 'down' | 'none' }

    const chatIdRef = useRef(initialChatId || null);
    const accumulatorRef = useRef("");
    const messagesRef = useRef([]);
    const { addOrUpdateChat } = useChatContext();

    // Keep messagesRef in sync so we can read latest messages outside of state
    const setMessagesAndRef = useCallback((updater) => {
        setMessages((prev) => {
            const next = typeof updater === "function" ? updater(prev) : updater;
            messagesRef.current = next;
            return next;
        });
    }, []);

    // Load history when opening an existing chat
    useEffect(() => {
        if (!initialChatId || typeof window === "undefined" || !window.electronAPI) return;
        window.electronAPI.getChats(userId).then((chats) => {
            const found = chats?.find((c) => c.chatId === initialChatId);
            if (found?.chatHistory?.length) {
                const msgs = historyToMessages(found.chatHistory);
                messagesRef.current = msgs;
                setMessages(msgs);
            }
        });
    }, [initialChatId, userId]);

    const chatTitleRef = useRef("New Chat");
    const titleSetRef = useRef(!!initialChatId);

    const saveChat = useCallback(async (updatedMessages) => {
        const cid = chatIdRef.current;
        if (!cid || !userId) return;

        const chatData = {
            chatId: cid,
            userId,
            chatTitle: chatTitleRef.current,
            chatHistory: messagesToHistory(updatedMessages),
            updatedAt: Date.now(),
        };

        addOrUpdateChat(chatData);

        if (typeof window !== "undefined" && window.electronAPI) {
            await window.electronAPI.saveChat(chatData);
        }
    }, [userId, addOrUpdateChat]);

    const streamResponse = useCallback(async (messageId, userPrompt, filePaths = []) => {
        setStreamingMessageId(messageId);
        accumulatorRef.current = "";

        // History = all completed messages (exclude the blank assistant placeholder we just added)
        const history = messagesRef.current
            .filter((m) => !(m.from === "assistant" && m.versions[0].id === messageId))
            .map((m) => ({
                role: m.from === "user" ? "user" : "assistant",
                content: m.versions[0].agentContent ?? m.versions[0].content,
            }))
            .filter((m) => m.content);

        try {
            await callAgentAPI({
                prompt: userPrompt,
                filePaths,
                history,
                userId,
                chatId: chatIdRef.current,
                onTextChunk: (chunk) => {
                    accumulatorRef.current += chunk;
                    const snapshot = accumulatorRef.current;
                    setMessagesAndRef((prev) =>
                        prev.map((msg) =>
                            msg.versions[0].id === messageId
                                ? { ...msg, versions: [{ ...msg.versions[0], content: snapshot }] }
                                : msg
                        )
                    );
                },
                onToolCall: ({ tool, detail }) => {
                    if (detail !== "done") setActiveToolName(tool);
                    else setActiveToolName(null);
                },
                onComplete: () => {
                    setActiveToolName(null);
                    setStreamingMessageId(null);
                    saveChat(messagesRef.current);
                },
                onError: (error) => {
                    console.error("API Error:", error);
                    setActiveToolName(null);
                    setStreamingMessageId(null);
                },
            });
        } catch {
            setActiveToolName(null);
            setStreamingMessageId(null);
        }
    }, [userId, saveChat]);

    const handleOnSubmit = useCallback(async (inputData) => {
        const content = inputData.text?.trim();
        const rawFiles = inputData.files || [];
        if (!content && rawFiles.length === 0) return;

        // Generate chatId on first message from / and update URL without remounting
        if (!chatIdRef.current) {
            const newId = nanoid();
            chatIdRef.current = newId;
            window.history.pushState(null, "", `/app/${newId}`);
        }

        const cid = chatIdRef.current;

        // Upload files to agent-server/user_stuff and get back absolute paths
        let filePaths = [];
        if (rawFiles.length > 0) {
            try {
                const form = new FormData();
                rawFiles.forEach(({ file }) => form.append("files", file));
                const res = await fetch("http://127.0.0.1:11435/upload", { method: "POST", body: form });
                const data = await res.json();
                filePaths = data.paths || [];
            } catch (e) {
                console.error("File upload failed:", e);
            }
        }

        // Build display content — show text + attached file names
        const fileNames = rawFiles.map(({ file }) => file.name).join(", ");
        const displayContent = content
            ? (filePaths.length > 0 ? `${content}\n[Attached: ${fileNames}]` : content)
            : `[Attached: ${fileNames}]`;

        // Full prompt sent to agent — file paths baked in so history replay works
        const agentContent = filePaths.length > 0
            ? `${content || ""}\nAttached files: ${filePaths.join(", ")}`.trim()
            : (content || "");

        // Image previews for inline display in the message bubble
        const imagePreviews = rawFiles
            .filter(({ isImage }) => isImage)
            .map(({ file, url }) => ({ name: file.name, url }));

        const userMessage = {
            from: "user",
            key: `user-${Date.now()}`,
            versions: [{
                content: displayContent,   // shown in UI
                agentContent,              // sent to agent + stored in history
                imagePreviews,             // inline image previews
                id: `user-idx-${Date.now()}`,
            }],
        };
        const assistantMessageId = `assistant-${Date.now()}`;
        const assistantMessage = {
            from: "assistant",
            key: `assistant-key-${Date.now()}`,
            versions: [{ content: "", id: assistantMessageId }],
        };
        setMessagesAndRef((prev) => [...prev, userMessage, assistantMessage]);

        // Set title once on first submit only
        if (!titleSetRef.current) {
            titleSetRef.current = true;
            const title = content && content.length >= 3
                ? (content.length > 60 ? content.slice(0, 57) + "..." : content)
                : "New Chat";
            chatTitleRef.current = title;
            const initialChatData = {
                chatId: cid,
                userId,
                chatTitle: title,
                chatHistory: [{ role: "user", content: displayContent }],
                updatedAt: Date.now(),
            };
            addOrUpdateChat(initialChatData);
            if (typeof window !== "undefined" && window.electronAPI) {
                window.electronAPI.saveChat(initialChatData);
            }
        }

        streamResponse(assistantMessageId, agentContent, []);
    }, [streamResponse, addOrUpdateChat, userId]);

    const handleOpenOverlay = () => {
        if (typeof window !== "undefined" && window.electronAPI) {
            window.electronAPI.openOverlay();
        }
    };

    return (
        <main className="flex-1 h-screen overflow-hidden relative py-1.5 px-1.5">
            <div className="bg-bg-modal h-[98vh] rounded-md border border-border-default flex flex-col relative">
                <div className="absolute top-2.5 left-2.5 z-30 flex gap-2 items-center">
                    <div
                        onClick={() => { const s = document.getElementById("sidebar"); s.setAttribute('data-state', s.getAttribute('data-state') === 'open' ? 'close' : 'open'); }}
                        className="md:hidden text-sm flex items-center justify-center hover:bg-bg-hover transition-all duration-100 cursor-pointer text-text-muted w-9 h-9 rounded-lg"
                    >
                        <PanelLeft24Regular />
                    </div>
                    <div onClick={handleOpenOverlay} className="text-sm flex items-center justify-center hover:bg-bg-hover transition-all duration-100 cursor-pointer text-text-muted w-9 h-9 rounded-lg">
                        <ArrowCircleUpRight24Regular />
                    </div>
                </div>

                <div data-showgreet={messages.length === 0} className="group data-[showgreet=true]:flex-[0.5] flex-1 overflow-y-auto">
                    <div className="group-data-[showgreet=true]:hidden max-w-3xl mx-auto w-full py-10 px-4 space-y-8">
                        {messages.map((msg) => (
                            <div key={msg.key}>
                                {msg.from === "user" && (
                                    <div className="flex flex-col items-end group">
                                        {msg.versions[0].imagePreviews?.length > 0 && (
                                            <div className="flex flex-wrap gap-2 mb-2 justify-end">
                                                {msg.versions[0].imagePreviews.map((img, i) => (
                                                    <img key={i} src={img.url} alt={img.name} className="max-h-48 max-w-xs rounded-xl object-cover border border-border-default" />
                                                ))}
                                            </div>
                                        )}
                                        <div className="bg-bg-hover text-text-primary px-4 py-2.5 rounded-2xl rounded-tr-sm max-w-[85%] text-base whitespace-pre-wrap">
                                            {msg.versions[0].content}
                                        </div>
                                        <span className="text-[10px] text-text-muted mt-1 opacity-0 group-hover:opacity-100 transition-opacity">Just now</span>
                                    </div>
                                )}
                                {msg.from === "assistant" && (
                                    <div className="flex flex-col items-start group">
                                        {/* RAI Label — task 11.1 */}
                                        <div
                                            data-testid="rai-label"
                                            className="flex items-center gap-1 mb-1"
                                            style={{ fontFamily: 'var(--font-body)', fontSize: 11, color: 'var(--text-muted)' }}
                                        >
                                            <Sparkle24Filled style={{ fontSize: 13, color: '#0078D4' }} />
                                            <span>
                                                {streamingMessageId === msg.versions[0].id ? "AI is responding…" : "AI-generated"}
                                            </span>
                                        </div>
                                        <div className="flex items-start gap-3 max-w-[90%]">
                                            <div className="space-y-4 pt-1">
                                                {streamingMessageId === msg.versions[0].id && (!msg.versions[0].content || activeToolName) ? (
                                                    <AgentLoader toolName={activeToolName} />
                                                ) : (
                                                    <div className="text-text-primary leading-relaxed xmarkdown-content">
                                                        <XMarkdown
                                                            content={msg.versions[0].content}
                                                            hasNextChunk={streamingMessageId === msg.versions[0].id}
                                                        />
                                                    </div>
                                                )}
                                                {streamingMessageId !== msg.versions[0].id && msg.versions[0].content && (
                                                    <>
                                                        {/* Feedback_Control — task 11.2 */}
                                                        <div
                                                            data-testid="feedback-control"
                                                            className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                                                        >
                                                            <Button
                                                                appearance="subtle"
                                                                icon={<ThumbLike24Filled style={{ color: feedbackState[msg.versions[0].id] === 'up' ? '#0078D4' : 'var(--text-muted)' }} />}
                                                                onClick={() => setFeedbackState(prev => ({ ...prev, [msg.versions[0].id]: prev[msg.versions[0].id] === 'up' ? 'none' : 'up' }))}
                                                                style={{ minWidth: 0 }}
                                                            />
                                                            <Button
                                                                appearance="subtle"
                                                                icon={<ThumbDislike24Filled style={{ color: feedbackState[msg.versions[0].id] === 'down' ? '#bc2f32' : 'var(--text-muted)' }} />}
                                                                onClick={() => setFeedbackState(prev => ({ ...prev, [msg.versions[0].id]: prev[msg.versions[0].id] === 'down' ? 'none' : 'down' }))}
                                                                style={{ minWidth: 0 }}
                                                            />
                                                            <Button
                                                                appearance="subtle"
                                                                icon={<Copy24Regular style={{ color: 'var(--text-muted)' }} />}
                                                                style={{ minWidth: 0 }}
                                                                onClick={() => safeCopy(msg.versions[0].content)}
                                                            />
                                                        </div>
                                                        {/* Verify_Nudge — task 11.3 */}
                                                        <p
                                                            data-testid="verify-nudge"
                                                            className="opacity-0 group-hover:opacity-100 transition-opacity"
                                                            style={{ fontFamily: 'var(--font-body)', fontSize: 11, color: 'var(--text-muted)' }}
                                                        >
                                                            Always verify AI responses before acting on them.
                                                        </p>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                <div className="w-full pb-6 pt-2">
                    {messages.length === 0 && (
                        <div
                            className="flex items-center justify-center gap-1.5 pb-2"
                            style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--text-muted)' }}
                        >
                            <Info16Regular style={{ color: '#0078D4', flexShrink: 0 }} />
                            <span>Airi can make mistakes. Verify important information.</span>
                        </div>
                    )}
                    <ChatInput
                        user_name={user_name}
                        showgreet={messages.length === 0}
                        handleOnSubmit={handleOnSubmit}
                    />
                </div>
            </div>
        </main>
    );
}

export default ChatMain;
