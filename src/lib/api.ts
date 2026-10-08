export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

/** Uploads get a longer bound; an unreachable API cannot leave controls busy forever. */
export async function api<T>(
  url: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const form = body instanceof FormData;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), form ? 120000 : 15000);
  try {
    const response = await fetch("/api" + url, {
      method,
      signal: controller.signal,
      headers: {
        "X-Storyroom": "local",
        ...(!form && body !== undefined
          ? { "Content-Type": "application/json" }
          : {}),
      },
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
    });
    if (!response.ok) {
      const data = await response
        .json()
        .catch(() => ({ detail: "Request failed" }));
      throw new ApiError(
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail),
        response.status,
      );
    }
    return await response.json();
  } catch (error) {
    if (controller.signal.aborted)
      throw new Error(
        "Request timed out. Check the local server, then retry. A save may have reached the server; reload before repeating it.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
