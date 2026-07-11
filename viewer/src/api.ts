// Thin client for the studio server's job + library endpoints. All localhost;
// nothing here talks to the network beyond the local process.
import { parseListenDocument } from "./loadListen";
import type { Job, LibraryEntry, ListenDocument } from "./types";

export interface SubmitOptions {
  enrich: boolean;
  gloss?: string; // "de" | "en" — only when enrich
  model?: string | null;
}

/** Submit an audio file as a background job. Returns the new job id. */
export async function submitJob(file: File, opts: SubmitOptions): Promise<string> {
  const params = new URLSearchParams({ enrich: opts.enrich ? "1" : "0" });
  if (opts.enrich && opts.gloss) {
    params.set("gloss", opts.gloss);
    if (opts.model) params.set("model", opts.model);
  }
  const resp = await fetch(`/jobs?${params.toString()}`, {
    method: "POST",
    headers: { "X-Filename": file.name },
    body: file,
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.message ?? `Serverfehler (${resp.status}).`);
  }
  return (await resp.json()).jobId as string;
}

/** Cancel a queued or running job (aborts at its next progress step). */
export async function cancelJob(id: string): Promise<void> {
  await fetch(`/jobs/${id}`, { method: "DELETE" });
}

export async function fetchJobs(): Promise<Job[]> {
  const resp = await fetch("/jobs");
  if (!resp.ok) return [];
  return ((await resp.json()).jobs ?? []) as Job[];
}

export async function fetchLibrary(): Promise<LibraryEntry[]> {
  const resp = await fetch("/library");
  if (!resp.ok) return [];
  return ((await resp.json()).entries ?? []) as LibraryEntry[];
}

/** Load a saved result's .listen.json into a validated ListenDocument. */
export async function fetchResult(id: string): Promise<ListenDocument> {
  const resp = await fetch(`/library/${id}/result`);
  if (!resp.ok) throw new Error(`Couldn't load entry (${resp.status}).`);
  return parseListenDocument(await resp.text());
}

/** The range-served audio URL for a saved entry (the <audio> element can seek it). */
export function audioUrl(id: string): string {
  return `/library/${id}/audio`;
}

/** Queue a re-translation of a saved entry into `lang` (reuses the transcript). */
export async function translateEntry(
  id: string,
  lang: string,
  model?: string | null,
): Promise<string> {
  const params = new URLSearchParams({ lang });
  if (model) params.set("model", model);
  const resp = await fetch(`/library/${id}/translate?${params.toString()}`, { method: "POST" });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.message ?? `Serverfehler (${resp.status}).`);
  }
  return (await resp.json()).jobId as string;
}

export async function deleteEntry(id: string): Promise<void> {
  await fetch(`/library/${id}`, { method: "DELETE" });
}

export async function deleteAudio(id: string): Promise<void> {
  await fetch(`/library/${id}/audio`, { method: "DELETE" });
}
