export async function callAgentAPI({ prompt, userId, chatId, onTextChunk, onComplete, onError }) {
    try {
        const response = await fetch("/api/agent", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt, userId, chatId }),
        });

        if (!response.ok) throw new Error(`API error: ${response.statusText}`);
        if (!response.body) throw new Error("No response body returned from the API.");

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let lastContent = "";

        while (true) {
            const { done, value } = await reader.read();

            if (done) {
                onComplete();
                break;
            }

            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || "";

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;

                try {
                    // agent.py yields the full message history list as NDJSON
                    // e.g. [{"role":"assistant","content":"Hello..."}]
                    const parsed = JSON.parse(trimmed);
                    const last = Array.isArray(parsed) ? parsed[parsed.length - 1] : parsed;
                    const content = last?.content ?? "";

                    if (typeof content === "string" && content.length > lastContent.length) {
                        // Send only the new delta
                        onTextChunk(content.slice(lastContent.length));
                        lastContent = content;
                    }
                } catch {
                    // incomplete chunk, will be retried with buffer
                }
            }
        }
    } catch (error) {
        console.error("Stream reading error:", error);
        onError(error);
    }
}
