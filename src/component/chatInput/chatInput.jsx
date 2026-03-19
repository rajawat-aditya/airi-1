"use client";

import { useState, useRef, useEffect, useCallback } from "react";

export default function ChatInput({
    showgreet,
    handleOnSubmit,
    user_name,
}) {
    const [message, setMessage] = useState({ text: "" });
    const [files, setFiles] = useState([]);
    const textareaRef = useRef(null);
    const fileInputRef = useRef(null);

    // Auto resize textarea
    useEffect(() => {
        const el = textareaRef.current;
        if (!el) return;

        el.style.height = "auto";
        el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }, [message?.text]);

    // Cleanup object URLs (prevents memory leak)
    useEffect(() => {
        return () => {
            files.forEach((f) => URL.revokeObjectURL(f.url));
        };
    }, [files]);

    // Handle file selection
    const handleFileChange = useCallback((e) => {
        const selected = Array.from(e.target.files || []);

        const previews = selected.map((file) => ({
            file,
            url: URL.createObjectURL(file),
            isImage: file.type.startsWith("image/"),
        }));

        setFiles((prev) => [...prev, ...previews]);
    }, []);

    // Remove file
    const removeFile = useCallback((index) => {
        setFiles((prev) => {
            const file = prev[index];
            if (file?.url) URL.revokeObjectURL(file.url);
            return prev.filter((_, i) => i !== index);
        });
    }, []);

    // Submit handler
    const submit = useCallback(() => {
        const text = message?.text?.trim();

        if (!text && files.length === 0) return;

        handleOnSubmit({ text, files });

        setMessage({ text: "" });
        setFiles([]);
    }, [message, files, handleOnSubmit, setMessage]);

    // ENTER TO SEND
    const handleKeyDown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
        }
    };

    return (
        <div className="w-full max-w-184 mx-auto px-4">

            {/* Greeting */}
            {showgreet && (
                <div className="flex text-[#e5ebfa] font-semibold w-full flex-col items-start justify-start sm:justify-end sm:mb-8 sm:h-25 text-2xl sm:ps-2">
                    <h2 className="text-[28px]">
                        Hi {user_name}, what should we dive into today?
                    </h2>
                </div>
            )}

            {/* Input Box */}
            <div className="bg-[#171a26] rounded-[28px] border border-[#ffffff14] shadow-lg focus-within:border-[#ffffff33]">

                {/* File Preview */}
                {files.length > 0 && (
                    <div className="flex flex-wrap gap-2 p-4 pb-0">
                        {files.map((file, i) => (
                            <div key={i} className="relative size-16 bg-[#ffffff0a] rounded-xl overflow-hidden border border-[#ffffff14]">
                                {file.isImage ? (
                                    <img src={file.url} className="w-full h-full object-cover" />
                                ) : (
                                    <div className="flex items-center justify-center h-full text-xs text-[#c2cadf] p-1 text-center">
                                        {file.file.name.split(".").pop().toUpperCase()}
                                    </div>
                                )}

                                <button
                                    onClick={() => removeFile(i)}
                                    className="absolute top-1 right-1 bg-black/60 text-white rounded-full size-5 flex items-center justify-center text-xs"
                                >
                                    ✕
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Textarea */}
                <div className="px-4 pt-4">
                    <textarea
                        ref={textareaRef}
                        rows={1}
                        value={message?.text || ""}
                        onChange={(e) =>
                            setMessage((prev) => ({
                                ...prev,
                                text: e.target.value,
                            }))
                        }
                        onKeyDown={handleKeyDown} // ENTER LOGIC
                        placeholder="Ask me anything..."
                        className="w-full bg-transparent text-[#e5ebfa] placeholder-[#c2cadf] outline-none resize-none text-[16px] max-h-[200px]"
                    />
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between p-3">

                    {/* File Button */}
                    <div>
                        <input
                            type="file"
                            multiple
                            ref={fileInputRef}
                            onChange={handleFileChange}
                            className="hidden"
                        />

                        <button
                            onClick={() => fileInputRef.current?.click()}
                            className="p-2 text-[#c2cadf] hover:bg-[#ffffff0a] rounded-full"
                        >
                            +
                        </button>
                    </div>

                    {/* Send Button */}
                    <button
                        onClick={submit}
                        disabled={!message?.text?.trim() && files.length === 0}
                        className={`size-10 rounded-full flex items-center justify-center transition ${message?.text?.trim() || files.length > 0
                                ? "bg-white text-black"
                                : "bg-[#ffffff0a] text-[#ffffff33]"
                            }`}
                    >
                        ↑
                    </button>
                </div>
            </div>
        </div>
    );
}