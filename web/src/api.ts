export async function request<T>(
  path: string,
  token = "",
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-AskLess-Token": token },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null);
    const detail =
      error && typeof error === "object" && "detail" in error
        ? (error as { detail: unknown }).detail
        : null;
    throw new Error(
      typeof detail === "string"
        ? detail
        : `请求失败 (${response.status})，请检查输入后重试。`,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
