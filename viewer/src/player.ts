// A thin wrapper over HTMLAudioElement adding an A–B sentence loop (for shadowing)
// and a stable rate control. No streaming, no network — a local object URL only.

export class Player {
  readonly audio: HTMLAudioElement;
  private loop: { start: number; end: number } | null = null;

  constructor() {
    this.audio = new Audio();
    this.audio.preload = "auto";
    this.audio.addEventListener("timeupdate", () => this.enforceLoop());
  }

  load(objectUrl: string): void {
    this.audio.src = objectUrl;
  }

  play(): Promise<void> {
    return this.audio.play();
  }
  pause(): void {
    this.audio.pause();
  }
  toggle(): void {
    if (this.audio.paused) void this.play();
    else this.pause();
  }
  get paused(): boolean {
    return this.audio.paused;
  }

  get currentTime(): number {
    return this.audio.currentTime;
  }
  seek(seconds: number): void {
    this.audio.currentTime = seconds;
  }
  get duration(): number {
    return Number.isFinite(this.audio.duration) ? this.audio.duration : 0;
  }

  setRate(rate: number): void {
    this.audio.playbackRate = rate;
  }

  setLoop(start: number, end: number): void {
    this.loop = { start, end };
    if (this.currentTime < start || this.currentTime >= end) this.seek(start);
  }
  clearLoop(): void {
    this.loop = null;
  }
  get looping(): boolean {
    return this.loop !== null;
  }

  private enforceLoop(): void {
    if (this.loop && this.audio.currentTime >= this.loop.end) {
      this.audio.currentTime = this.loop.start;
    }
  }
}
