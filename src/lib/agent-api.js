export async function callAgentAPI({ prompt, history = [], userId, chatId, onTextChunk, onComplete, onError }) {
    const agentUrl = typeof window !== "undefined" && window.electronAPI
        ? "http://127.0.0.1:11435/v1/chat/completions"
        : "/api/agent";

    // prompt already has "Attached files: ..." baked in when files are present (built in chatMain)
    const messages = [...history, { role: "user", content: prompt }];

    try {
        const response = await fetch(agentUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(
                agentUrl.includes("11435")
                    ? { model: "airi", stream: true, messages, user_id: userId ?? "default_user", session_id: chatId ?? "default_session" }
                    : { messages, userId, chatId }
            ),
        });

        if (!response.ok) throw new Error(`API error: ${response.statusText}`);
        if (!response.body) throw new Error("No response body returned from the API.");

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed || !trimmed.startsWith("data: ")) continue;

                const data = trimmed.slice(6);
                if (data === "[DONE]") { onComplete(); return; }

                try {
                    const parsed = JSON.parse(data);
                    const content = parsed?.choices?.[0]?.delta?.content;
                    if (content) onTextChunk(content);
                } catch {
                    // incomplete chunk — wait for next read
                }
            }
        }
        onComplete();
    } catch (error) {
        console.error("Stream reading error:", error);
        onError(error);
    }
}
