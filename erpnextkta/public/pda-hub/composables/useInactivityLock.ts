import { ref, watch, onMounted, onUnmounted, type Ref } from "vue";

const DEFAULT_TIMEOUT_MS = 300_000;
const ACTIVITY_EVENTS = ["pointerdown", "keydown", "touchstart", "click"] as const;

export function useInactivityLock(options: {
  timeoutMs?: number;
  enabled: Ref<boolean>;
  onLock: () => void;
}) {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const remainingSeconds = ref<number>(Math.ceil(timeoutMs / 1000));

  let lockTimer: ReturnType<typeof setTimeout> | null = null;
  let tickTimer: ReturnType<typeof setInterval> | null = null;
  let deadlineMs = 0;

  function clearTimers() {
    if (lockTimer !== null) {
      clearTimeout(lockTimer);
      lockTimer = null;
    }
    if (tickTimer !== null) {
      clearInterval(tickTimer);
      tickTimer = null;
    }
  }

  function resetTimer() {
    clearTimers();
    remainingSeconds.value = Math.ceil(timeoutMs / 1000);
    if (!options.enabled.value) return;

    deadlineMs = Date.now() + timeoutMs;
    lockTimer = setTimeout(() => {
      clearTimers();
      remainingSeconds.value = 0;
      if (options.enabled.value) {
        options.onLock();
      }
    }, timeoutMs);

    tickTimer = setInterval(() => {
      const left = Math.max(0, Math.ceil((deadlineMs - Date.now()) / 1000));
      remainingSeconds.value = left;
    }, 1000);
  }

  function handleActivity() {
    if (options.enabled.value) {
      resetTimer();
    }
  }

  function attachListeners() {
    if (typeof window === "undefined") return;
    ACTIVITY_EVENTS.forEach((evt) =>
      window.addEventListener(evt, handleActivity, { passive: true })
    );
  }

  function detachListeners() {
    if (typeof window === "undefined") return;
    ACTIVITY_EVENTS.forEach((evt) =>
      window.removeEventListener(evt, handleActivity)
    );
  }

  watch(
    () => options.enabled.value,
    (isEnabled) => {
      if (isEnabled) resetTimer();
      else clearTimers();
    },
    { immediate: true }
  );

  onMounted(() => {
    attachListeners();
    if (options.enabled.value) resetTimer();
  });

  onUnmounted(() => {
    clearTimers();
    detachListeners();
  });

  return {
    remainingSeconds,
    resetTimer,
  };
}
