// Copyright (c) 2026, KTA and Contributors
// See license.txt

let audioCtxSingleton: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (!audioCtxSingleton) {
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;

    if (AudioContextClass) {
      audioCtxSingleton = new AudioContextClass();
    }
  }
  return audioCtxSingleton;
}

/**
 * Web Audio API audio feedback utility for PDA handheld terminals.
 * Uses a singleton AudioContext to prevent Chromium AudioContext exhaustion.
 * Plays an 800Hz sine wave beep on success, or a 300Hz sawtooth buzz on error.
 */
export async function playBeep(success: boolean): Promise<void> {
  try {
    if (
      typeof localStorage !== "undefined" &&
      localStorage.getItem("kta_pda_sound") === "0"
    ) {
      return;
    }
  } catch {
    // Ignore localStorage access errors.
  }

  try {
    const ctx = getAudioContext();
    if (!ctx) {
      return;
    }

    if (ctx.state === "suspended") {
      await ctx.resume();
    }

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.connect(gain);
    gain.connect(ctx.destination);

    if (success) {
      osc.type = "sine";
      osc.frequency.setValueAtTime(800, ctx.currentTime);
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    } else {
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(300, ctx.currentTime);
      gain.gain.setValueAtTime(0.35, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
    }
  } catch {
    // Gracefully ignore audio errors (e.g. device without audio hardware or blocked autoplay)
  }
}
