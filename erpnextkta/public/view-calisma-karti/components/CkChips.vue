<script setup lang="ts">
const props = defineProps<{
  durumLabel: string;
  statusClass: string;
  qcLabel: string;
  qcClass: string;
}>();
</script>

<template>
  <div class="ck-chips-bar" :class="props.statusClass">
    <!-- Left Section: Status -->
    <div class="ck-bar-section ck-status-section">
      <div v-if="props.statusClass.includes('running')" class="ck-pulse-dot"></div>
      <span class="ck-status-text">{{ props.durumLabel }}</span>
    </div>

    <!-- Middle Divider (Decorative) -->
    <div class="ck-bar-divider"></div>

    <!-- Right Section: QC -->
    <div class="ck-bar-section ck-qc-section" :class="props.qcClass">
      <span class="ck-qc-tag">QC</span>
      <span class="ck-status-text">{{ props.qcLabel }}</span>
    </div>
  </div>
</template>

<style scoped>
.ck-chips-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 12px 0 16px;
  padding: 10px 20px;
  border-radius: 16px;
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border);
  box-shadow: var(--ck-glass-shadow), var(--ck-glass-highlight);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
  position: relative;
}

.ck-chips-bar::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(90deg, currentColor 0%, transparent 50%, currentColor 100%);
  opacity: 0.03;
  pointer-events: none;
}

.ck-bar-section {
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 1;
}

.ck-status-text {
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: inherit;
}

.ck-bar-divider {
  flex: 1;
  height: 1px;
  background: var(--ck-glass-border-soft);
  margin: 0 24px;
  opacity: 0.5;
}

.ck-qc-tag {
  font-size: 10px;
  font-weight: 950;
  opacity: 0.5;
  padding: 2px 6px;
  border: 1px solid currentColor;
  border-radius: 6px;
}

/* Pulse Animation for Status Dot */
.ck-pulse-dot {
  width: 10px;
  height: 10px;
  background: currentColor;
  border-radius: 50%;
  position: relative;
}

.ck-pulse-dot::after {
  content: '';
  position: absolute;
  top: 0; left: 0; 
  width: 100%; height: 100%;
  background: inherit;
  border-radius: inherit;
  animation: ck-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes ck-pulse {
  0% { transform: scale(1); opacity: 0.8; }
  100% { transform: scale(3.5); opacity: 0; }
}

/* --- THEME-FRIENDLY COLOR STATES (APPLIED TO BAR) --- */

.ck-status--ready {
  color: #2563eb;
  border-color: rgba(37, 99, 235, 0.25);
  box-shadow: 0 0 20px rgba(37, 99, 235, 0.05), var(--ck-glass-highlight);
}

.ck-status--running {
  color: #059669;
  border-color: rgba(5, 150, 105, 0.3);
  box-shadow: 0 0 25px rgba(5, 150, 105, 0.08), var(--ck-glass-highlight);
}

.ck-status--paused {
  color: #d97706;
  border-color: rgba(217, 119, 6, 0.3);
}

.ck-status--finished {
  color: #059669;
}

.ck-status--rejected {
  color: #dc2626;
  border-color: rgba(220, 38, 38, 0.3);
}

.ck-status--cancelled {
  color: #4b5563;
  opacity: 0.8;
}

/* QC Specific coloring within the bar */
.ck-qc-section.ck-status-qc--rejected {
  color: #dc2626;
}

.ck-qc-section.ck-status-qc--running {
  color: #059669;
}

.ck-qc-section.ck-status-qc--pending {
  color: #2563eb;
}

/* Dark Mode Intensity Adjustments */
[data-theme="dark"] .ck-chips-bar {
  background: rgba(255, 255, 255, 0.03);
}

[data-theme="dark"] .ck-status--ready { color: #60a5fa; }
[data-theme="dark"] .ck-status--running { color: #34d399; }
[data-theme="dark"] .ck-status--paused { color: #fbbf24; }
[data-theme="dark"] .ck-status--finished { color: #34d399; }
[data-theme="dark"] .ck-status--rejected { color: #f87171; }

/* Responsive adjustments for mobile */
@media screen and (max-width: 767px) {
  .ck-chips-bar {
    padding: 8px 14px;
    margin: 8px 0 12px;
    border-radius: 12px;
    gap: 8px;
  }

  .ck-status-text {
    font-size: 11px;
    letter-spacing: 0.05em;
  }

  .ck-bar-divider {
    margin: 0 12px;
    opacity: 0.3;
  }

  .ck-qc-tag {
    font-size: 9px;
    padding: 1px 4px;
    border-radius: 4px;
  }

  .ck-bar-section {
    gap: 8px;
  }

  .ck-pulse-dot {
    width: 8px;
    height: 8px;
  }
}
</style>