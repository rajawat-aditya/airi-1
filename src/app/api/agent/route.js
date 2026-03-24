// 1 hour timeout — agent tasks can take a long time
export const maxDuration = 3600;

export async function POST(request) {
  try {
    const { messages = [], userId, chatId } = await request.json();

    const response = await fetch("http://localhost:11435/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(3600_000),
      body: JSON.stringify({
        model: "airi",
        stream: true,
        messages,
        user_id: userId,
        session_id: chatId,
      }),
    });

    if (!response.ok) {
      return new Response(
        JSON.stringify({ error: `Backend request failed: ${response.statusText}` }),
        { status: response.status, headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response(response.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      },
    });
  } catch (error) {
    console.error("API Route Error:", error);
    return new Response(
      JSON.stringify({ error: "Failed to process request", details: error.message }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}

export async function OPTIONS() {
  return new Response(null, {
    status: 200,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
