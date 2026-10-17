'use client';

type SoundKind = 'click' | 'success' | 'error' | 'tick';

let context: AudioContext | null = null;

function audioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!context) context = new Ctor();
  if (context.state === 'suspended') void context.resume();
  return context;
}

function beep(frequency: number, duration: number, type: OscillatorType, volume: number, delay = 0) {
  const ctx = audioContext();
  if (!ctx) return;
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = type;
  oscillator.frequency.value = frequency;
  gain.gain.setValueAtTime(0.0001, ctx.currentTime + delay);
  gain.gain.exponentialRampToValueAtTime(volume, ctx.currentTime + delay + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + delay + duration);
  oscillator.connect(gain).connect(ctx.destination);
  oscillator.start(ctx.currentTime + delay);
  oscillator.stop(ctx.currentTime + delay + duration + 0.02);
}

export function playSound(kind: SoundKind, enabled: boolean): void {
  if (!enabled) return;
  try {
    if (kind === 'click') beep(660, 0.06, 'square', 0.05);
    if (kind === 'tick') beep(440, 0.03, 'square', 0.03);
    if (kind === 'success') {
      beep(523, 0.09, 'square', 0.06, 0);
      beep(659, 0.09, 'square', 0.06, 0.1);
      beep(784, 0.16, 'square', 0.07, 0.2);
    }
    if (kind === 'error') {
      beep(196, 0.12, 'sawtooth', 0.06, 0);
      beep(147, 0.2, 'sawtooth', 0.06, 0.12);
    }
  } catch {
    /* audio is optional */
  }
}
