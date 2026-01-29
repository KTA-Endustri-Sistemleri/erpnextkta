<script setup lang="ts">
import { computed } from "vue";
import { barcodeBars, barX, barOpacity } from "../utils/kalite_ui";

const props = defineProps<{
  value: string;
  width?: number; // optional
}>();

const bars = computed(() => barcodeBars(props.value));
const svgWidth = computed(() => Number(props.width || 140));
</script>

<template>
  <div
    aria-label="Barkod görseli"
    style="height: 34px;border: 1px solid rgba(0, 0, 0, 0.08);border-radius: 10px;padding: 6px 10px;background: rgb(255, 255, 255);display: flex;align-items: center;justify-content: center;"
  >
    <svg :width="svgWidth" :height="22" :viewBox="`0 0 ${svgWidth} 22`" role="img" aria-hidden="true">
      <g>
        <template v-for="(w, idx) in bars" :key="idx">
          <rect
            :x="barX(bars, idx)"
            y="0"
            :width="w"
            height="22"
            fill="#111"
            :opacity="barOpacity(idx)"
          />
        </template>
      </g>
    </svg>
  </div>
</template>
