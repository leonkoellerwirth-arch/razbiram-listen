import { describe, expect, it } from "vitest";
import { fmtDuration, hasActive, isActive, jobProgress, newlyDone, queueJobs } from "../src/queue";
import type { Job } from "../src/types";

function job(partial: Partial<Job>): Job {
  return {
    id: "x",
    filename: "f.mp3",
    title: "f",
    status: "queued",
    createdAt: "",
    mode: "core",
    ...partial,
  };
}

describe("queue helpers", () => {
  it("isActive / hasActive", () => {
    expect(isActive(job({ status: "queued" }))).toBe(true);
    expect(isActive(job({ status: "running" }))).toBe(true);
    expect(isActive(job({ status: "done" }))).toBe(false);
    expect(isActive(job({ status: "error" }))).toBe(false);
    expect(hasActive([job({ status: "done" }), job({ status: "running" })])).toBe(true);
    expect(hasActive([job({ status: "done" })])).toBe(false);
  });

  it("queueJobs drops done jobs (they live in the library)", () => {
    const jobs = [
      job({ id: "a", status: "done" }),
      job({ id: "b", status: "running" }),
      job({ id: "c", status: "error" }),
    ];
    expect(queueJobs(jobs).map((j) => j.id)).toEqual(["b", "c"]);
  });

  it("newlyDone finds transitions to done since the last snapshot", () => {
    const prev = [job({ id: "a", status: "running" }), job({ id: "b", status: "done" })];
    const cur = [job({ id: "a", status: "done" }), job({ id: "b", status: "done" })];
    expect(newlyDone(prev, cur)).toEqual(["a"]);
  });

  it("fmtDuration formats mm:ss and h:mm:ss", () => {
    expect(fmtDuration(0)).toBe("0:00");
    expect(fmtDuration(75)).toBe("1:15");
    expect(fmtDuration(3661)).toBe("1:01:01");
    expect(fmtDuration(null)).toBe("");
    expect(fmtDuration(undefined)).toBe("");
  });

  it("jobProgress maps stages to labels and bar state", () => {
    expect(jobProgress(job({ status: "queued" })).label).toContain("Waiting");
    expect(
      jobProgress(job({ status: "running", stage: "transcribe", fraction: 0.5 })).label,
    ).toContain("50%");
    const enrichAnalysing = jobProgress(job({ status: "running", stage: "enrich", fraction: null }));
    expect(enrichAnalysing.indeterminate).toBe(true);
    expect(
      jobProgress(job({ status: "running", stage: "enrich", fraction: 0.5 })).label,
    ).toContain("Translating");
    expect(jobProgress(job({ status: "error", error: "boom" })).label).toBe("boom");
  });
});
