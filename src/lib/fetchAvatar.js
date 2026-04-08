/**
 * Fetch a remote image URL and return it as a base64 string.
 * Returns null on any error (rate-limit, network, etc.).
 */
export async function fetchAvatarBase64(url) {
    if (!url) return null;
    try {
        const res = await fetch(url);
        if (!res.ok) return null;
        const buffer = await res.arrayBuffer();
        const contentType = res.headers.get("content-type") || "image/png";
        return `data:${contentType};base64,${Buffer.from(buffer).toString("base64")}`;
    } catch {
        return null;
    }
}
