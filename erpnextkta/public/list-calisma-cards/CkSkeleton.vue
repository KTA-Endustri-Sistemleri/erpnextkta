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
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.ck-skel {
  display: grid;
  gap: 12px;
}

.ck-skel-card {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, .08);
  border-radius: 18px;
  overflow: hidden;
  height: 140px;
}

.ck-skel-pill {
  background: linear-gradient(90deg, #e5e7eb 25%, #f3f4f6 50%, #e5e7eb 75%);
  background-size: 200% 100%;
  animation: ck-shimmer 2s infinite linear;
  border-radius: 18px 0 0 18px;
}

.ck-skel-line {
  background: linear-gradient(90deg, #f3f4f6 25%, #f9fafb 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: ck-shimmer 2s infinite linear;
  border-radius: 8px;
}

.ck-skel-kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.ck-skel-chevron {
  width: 12px;
  height: 24px;
  background: #f3f4f6;
  border-radius: 4px;
}

.w60 { width: 60%; }
.w40 { width: 40%; }
.w80 { width: 80%; }
</style>
