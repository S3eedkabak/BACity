// Public content is opened in the browser, never as executable/custom schemes.
export function safeExternalUrl(value: unknown): string | null {
  if (typeof value !== 'string' || value.length > 4096 || /[\s\u0000-\u001f\u007f\\]/.test(value)) return null;
  const match = /^https?:\/\/([^/?#]+)(?:[/?#].*)?$/i.exec(value);
  if (!match || match[1].includes('@')) return null;
  return value;
}
