export function serializeRequestBody(body: unknown): string | undefined {
  return body === undefined ? undefined : JSON.stringify(body);
}
