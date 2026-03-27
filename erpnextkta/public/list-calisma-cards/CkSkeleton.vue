<template>
  <div class="ck-skel">
    <div v-for="i in count" :key="i" class="ck-skel-card">
      <div class="row no-gutters h-100">
        <div class="col-2 p-0 ck-skel-pill"></div>
        <div class="col-9 py-2 pl-2">
          <div class="ck-skel-line w60 mb-3" style="height: 16px;"></div>
          <div class="ck-skel-kv">
            <div v-for="j in 4" :key="j" class="ck-skel-kv-item">
              <div class="ck-skel-line w40 mb-1" style="height: 10px; opacity: 0.6;"></div>
              <div class="ck-skel-line w80" style="height: 12px;"></div>
            </div>
          </div>
        </div>
        <div class="col-1 p-0 d-flex align-items-center justify-content-center">
          <div class="ck-skel-chevron"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  count: {
    type: Number,
    default: 6
  }
});
</script>

<style scoped>
@keyframes ck-shimmer {
  0% { transform: translateX(-150%); }
  100% { transform: translateX(150%); }
}

.ck-skel {
  display: grid;
  gap: 12px;
}

.ck-skel-card {
  background: var(--ck-glass-bg, rgba(255, 255, 255, 0.6));
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--ck-glass-border-soft, rgba(0, 0, 0, 0.05));
  border-top: 1px solid var(--ck-glass-highlight, rgba(255, 255, 255, 0.8));
  box-shadow: 0 4px 12px var(--ck-glass-shadow, rgba(0, 0, 0, 0.03));
  border-radius: 18px;
  overflow: hidden;
  height: 140px;
  position: relative;
}

/* Base shape styles */
.ck-skel-pill {
  background: var(--ck-glass-border, rgba(0,0,0,0.04));
  border-radius: 18px 0 0 18px;
  height: 100%;
}

.ck-skel-line {
  background: var(--ck-glass-border, rgba(0,0,0,0.04));
  border-radius: 8px;
}

.ck-skel-chevron {
  width: 12px;
  height: 24px;
  background: var(--ck-glass-border, rgba(0,0,0,0.04));
  border-radius: 4px;
}

/* Global Shimmer Overlay for the whole card */
.ck-skel-card::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    var(--ck-skeleton-shine, rgba(255, 255, 255, 0.4)) 45%,
    var(--ck-skeleton-shine, rgba(255, 255, 255, 0.4)) 55%,
    rgba(255, 255, 255, 0) 100%
  );
  animation: ck-shimmer 1s infinite ease-in-out;
  pointer-events: none;
}

.ck-skel-kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.w60 { width: 60%; }
.w40 { width: 40%; }
.w80 { width: 80%; }
</style>
