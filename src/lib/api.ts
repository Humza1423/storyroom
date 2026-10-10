export type ErrorRecovery = {
  code?: string;
  scope?: "file" | "batch";
  uncertain?: boolean;
};

export class ApiError extends Error {
  public code?: string;
  public scope?: "file" | "batch";
  public uncertain: boolean;
  constructor(
    message: string,
    public status: number,
    recovery: ErrorRecovery = {},
  ) {
    super(message);
    this.code = recovery.code;
    this.scope = recovery.scope;
    this.uncertain = recovery.uncertain ?? (status === 0 || status >= 500);
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
        { code: data.code, scope: data.scope, uncertain: data.uncertain },
      );
    }
    return await response.json();
  } catch (error) {
    if (controller.signal.aborted)
      throw new ApiError(
        "Request timed out. It may have reached the server. Check saved work before retrying.",
        0,
        { code: "timeout", scope: "batch", uncertain: true },
      );
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "Could not confirm the response from the local server. The request may have reached it.",
      0,
      { code: "network", scope: "batch", uncertain: true },
    );
  } finally {
    clearTimeout(timer);
  }
}
