import { onMounted, onUnmounted, ref } from "vue";

export function useScrollSubbar(enabled: () => boolean) {
  const isSubbarHidden = ref<boolean>(false);
  let lastScrollY = 0;

  function getScrollY(): number {
    if (typeof window === "undefined") return 0;
    return window.scrollY || document.documentElement?.scrollTop || 0;
  }

  function onScroll() {
    const currentY = getScrollY();
    if (!enabled()) {
      isSubbarHidden.value = false;
      lastScrollY = currentY;
      return;
    }

    if (currentY <= 24) {
      isSubbarHidden.value = false;
    } else if (currentY > 48 && currentY - lastScrollY > 6) {
      isSubbarHidden.value = true;
    } else if (lastScrollY - currentY > 4) {
      isSubbarHidden.value = false;
    }

    lastScrollY = currentY;
  }

  function resetSubbar() {
    isSubbarHidden.value = false;
    lastScrollY = 0;
  }

  onMounted(() => {
    if (typeof window === "undefined") return;
    lastScrollY = getScrollY();
    window.addEventListener("scroll", onScroll, { passive: true });
  });

  onUnmounted(() => {
    if (typeof window === "undefined") return;
    window.removeEventListener("scroll", onScroll);
  });

  return {
    isSubbarHidden,
    resetSubbar,
  };
}
