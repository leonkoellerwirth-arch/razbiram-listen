import type { ListenDocument } from "./types";

/** Parse and shape-check a `.listen.json`. Permissive on optional fields, strict
 *  on the one thing the viewer needs: a `sentences` array. */
export function parseListenDocument(text: string): ListenDocument {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new ListenError("The file is not valid JSON.");
  }
  if (data === null || typeof data !== "object") {
    throw new ListenError("Das ist keine .listen.json.");
  }
  const doc = data as Record<string, unknown>;
  if (!Array.isArray(doc.sentences)) {
    throw new ListenError("This doesn't look like a .listen.json — sentences are missing.");
  }
  return data as ListenDocument;
}

export class ListenError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ListenError";
  }
}
