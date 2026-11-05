/** Hand a question to the workbench from another page: stored for one read, then the workbench puts it in the input. */
const KEY = "prefillPrompt";

export function setPrefill(text: string): void {
  try {
    sessionStorage.setItem(KEY, text);
  } catch {}
}

export function takePrefill(): string | null {
  try {
    const v = sessionStorage.getItem(KEY);
    if (v !== null) sessionStorage.removeItem(KEY);
    return v;
  } catch {
    return null;
  }
}
