<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  measured: number | null | undefined;
  target: number | null | undefined;
  unit?: string;
  tolerance?: number;
  segmentStep?: number;
  textLow?: string;
  textHigh?: string;
}>();

const TOTAL_SEGMENTS = 10; // her yarıda 10 segment

const hasData = computed(
  () =>
    props.measured != null &&
    props.measured > 0 &&
    props.target != null &&
    props.target > 0
);

// Fark (mm cinsinden): negatif → kısa, pozitif → uzun
const diff_mm = computed(() => {
  if (!hasData.value) return 0;
  return Number(
    ((props.measured as number) - (props.target as number)).toFixed(3)
  );
});

const safeTolerance = computed(() => props.tolerance || 0);
const safeStep = computed(() => props.segmentStep || 1);

const isLow  = computed(() => diff_mm.value < -safeTolerance.value - 0.001);
const isHigh = computed(() => diff_mm.value >  safeTolerance.value + 0.001);
const isOk   = computed(() => !isLow.value && !isHigh.value);

// Kaç kutu dolacak: 1 kutu = segmentStep değeri, maksimum 10
const filledCount = computed(() =>
  Math.min(Math.round(Math.abs(diff_mm.value) / safeStep.value), TOTAL_SEGMENTS)
);

// Sınır aşıldı mı? (TOTAL_SEGMENTS * segmentStep)
const limitMax = computed(() => Number((TOTAL_SEGMENTS * safeStep.value).toFixed(3)));
const isOverLimit = computed(() => Math.abs(diff_mm.value) > limitMax.value);

type SegmentState = "left-red" | "left-green" | "left-empty" | "right-green" | "right-red" | "right-empty";

const leftSegments = computed<SegmentState[]>(() => {
  return Array.from({ length: TOTAL_SEGMENTS }, (_, i) => {
    if (diff_mm.value < 0) {
      if (i >= TOTAL_SEGMENTS - filledCount.value) {
        return isOk.value ? "left-green" : "left-red";
      }
    }
    return "left-empty";
  });
});

const rightSegments = computed<SegmentState[]>(() => {
  return Array.from({ length: TOTAL_SEGMENTS }, (_, i) => {
    if (diff_mm.value > 0) {
      if (i < filledCount.value) {
        return isOk.value ? "right-green" : "right-red";
      }
    }
    return "right-empty";
  });
});
</script>

<template>
  <div v-if="!hasData" class="mg-na">—</div>

  <div v-else class="mg-root">
    <!-- Üst satır: ölçülen değer (sol/sağ konumlanır) + hedef etiketi -->
    <div class="mg-labels">
      <span
        class="mg-measured-label"
        :class="{
          'mg-label--low': isLow,
          'mg-label--high': isHigh,
          'mg-label--ok': isOk,
        }"
      >
        {{ measured }}<small v-if="unit"> {{ unit }}</small>
      </span>
      <span class="mg-target-label">
        {{ __('Hedef:') }} {{ target }}<small v-if="unit"> {{ unit }}</small>
        <span v-if="tolerance"> ±{{ tolerance }}</span>
      </span>
    </div>

    <!-- Çubuk -->
    <div class="mg-bar-row">
      <!-- Sol segmentler -->
      <div class="mg-half mg-half--left">
        <span
          v-for="(seg, i) in leftSegments"
          :key="'l' + i"
          class="mg-seg"
          :class="seg"
        />
      </div>

      <!-- Orta etiket: hedef değeri -->
      <div
        class="mg-center-pin"
        :class="{
          'mg-pin--low': isLow,
          'mg-pin--high': isHigh,
          'mg-pin--ok': isOk,
        }"
      >
        {{ target }}
      </div>

      <!-- Sağ segmentler -->
      <div class="mg-half mg-half--right">
        <span
          v-for="(seg, i) in rightSegments"
          :key="'r' + i"
          class="mg-seg"
          :class="seg"
        />
      </div>
    </div>

    <!-- Alt satır: fark -->
    <div class="mg-diff" :class="{ 'mg-diff--low': isLow, 'mg-diff--high': isHigh, 'mg-diff--ok': isOk }">
      <template v-if="isOk">✓ {{ __('Hedef karşılandı') }}</template>
      <template v-else-if="isLow">▼ {{ Math.abs(diff_mm) }} {{ unit }} {{ textLow ? __(textLow) : __('kısa') }}</template>
      <template v-else>▲ {{ diff_mm }} {{ unit }} {{ textHigh ? __(textHigh) : __('uzun') }}</template>
    </div>

    <!-- ± sınır uyarısı -->
    <div v-if="isOverLimit" class="mg-warning">
      ⚠ {{ __('Grafik sınırı') }} (±{{ limitMax }}) {{ __('aşıldı') }}!
    </div>
  </div>
</template>

<style scoped>
.mg-na {
  font-size: 13px;
  opacity: 0.4;
  padding: 4px 0;
}

.mg-root {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 100%;
  padding: 2px 0;
}

/* --- Üst etiket satırı --- */
.mg-labels {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 11px;
}

.mg-measured-label {
  font-size: 15px;
  font-weight: 800;
  line-height: 1;
}
.mg-measured-label small {
  font-size: 10px;
  font-weight: 400;
  opacity: 0.7;
}

.mg-label--low  { color: #cc2200; }
.mg-label--high { color: #cc2200; }
.mg-label--ok   { color: #1a7a1a; }

.mg-target-label {
  font-size: 10px;
  opacity: 0.5;
}
.mg-target-label small {
  opacity: 0.7;
}

/* --- Çubuk --- */
.mg-bar-row {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
}

.mg-half {
  display: flex;
  gap: 2px;
  flex: 1;
}
.mg-half--left  { justify-content: flex-end; }
.mg-half--right { justify-content: flex-start; }

.mg-seg {
  width: 8px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
  transition: background 0.2s, border-color 0.2s;
}

/* Dolu kırmızı (düşük - sol taraf / fazla - sağ taraf) */
.mg-seg.left-red,
.mg-seg.right-red {
  background: #cc2200;
  border: 1px solid #cc2200;
}

/* Boş kenarlık (sapma olmayan taraflar) */
.mg-seg.right-empty,
.mg-seg.left-empty {
  background: transparent;
  border: 1px solid var(--border-color, rgba(128, 128, 128, 0.3));
}

/* Dolu yeşil (tolerans içi - sol veya sağ) */
.mg-seg.right-green,
.mg-seg.left-green {
  background: #22a022;
  border: 1px solid #22a022;
}

/* --- Orta pin: hedef değeri --- */
.mg-center-pin {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 5px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
}
.mg-pin--low  { background: #ffe6e0; color: #cc2200; }
.mg-pin--high { background: #ffe6e0; color: #cc2200; }
.mg-pin--ok   { background: #e0f5e0; color: #1a7a1a; }

/* --- Alt fark etiketi --- */
.mg-diff {
  font-size: 10px;
  font-weight: 600;
  text-align: center;
  opacity: 0.85;
}
.mg-diff--low  { color: #cc2200; }
.mg-diff--high { color: #cc2200; }
.mg-diff--ok   { color: #1a7a1a; }

/* --- ±10 mm uyarı bandı --- */
.mg-warning {
  font-size: 10px;
  font-weight: 700;
  text-align: center;
  background: #ffe6e0;
  color: #cc2200;
  border: 1px solid #ffb3a0;
  border-radius: 6px;
  padding: 3px 8px;
}
</style>
