<template>
  <button class="ck-card" @click="$emit('click')">
    <div class="row no-gutters" :class="qcClasses">
      <div class="col-2 p-0 ck-pill" :data-tone="statusTone">
        <span>{{ row.durum || "-" }}</span>
      </div>
      <div class="col-9 py-2 pl-2">
        <div class="ck-name">{{ row.operator }}</div>
        <div class="ck-kv">
          <div class="ck-kv-item" style="display:flex; align-items:flex-start;">
            <div>
              <span>Ürün Kodu</span>
              <b>{{ row.urun_kodu || "-" }}</b>
            </div>
            <div v-if="row.custom_musteri_indeksi_no" style="text-align: left;margin-left: 10px;">
              <span>Index (Revision)</span>
              <b>
                {{ row.custom_musteri_indeksi_no }}
              </b>
            </div>
          </div>

          <div class="ck-kv-item">
            <span>İş Emri</span>
            <b>{{ row.custom_work_order || "-" }}</b>
          </div>
          <div class="ck-kv-item">
            <span>İş Kartı</span>
            <b>{{ row.is_karti || "-" }}</b>
          </div>
          <div class="ck-kv-item">
            <span>Operasyon</span>
            <b>{{ row.operasyon || "-" }}</b>
          </div>
        </div>
      </div>
      <div class="col-1 p-0 d-flex align-items-center">
        <span class="ck-chevron">›</span>
      </div>
    </div>
  </button>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  row: {
    type: Object,
    required: true
  }
});

defineEmits(["click"]);

const qcClasses = computed(() => ({
  "ck-status-card-qc--running": props.row.kalite_kontrol === "Onaylandı",
  "ck-status-card-qc--rejected": props.row.kalite_kontrol === "Reddedildi",
  "ck-status-card-qc--pending": props.row.kalite_kontrol === "Onay Bekliyor",
}));

const statusTone = computed(() => {
  const v = (props.row.durum || "").toLowerCase();
  if (v.includes("redd")) return "rejected";
  if (v.includes("bit")) return "finished";
  if (v.includes("duru")) return "paused";
  if (v.includes("çalı") || v.includes("calis")) return "running";
  if (v.includes("haz")) return "ready";
  return "ready";
});
</script>

<style scoped>
.ck-card {
  width: 100%;
  text-align: left;
  background: var(--ck-glass-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--ck-glass-border-soft);
  border-top: 1px solid var(--ck-glass-highlight);
  border-bottom: 1px solid var(--ck-glass-bottom-edge);
  border-radius: 18px;
  padding: 0;
  box-shadow: 0 4px 12px var(--ck-glass-shadow);
  margin-bottom: 12px;
  display: block;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.ck-card:active {
  transform: scale(.985);
  box-shadow: 0 2px 6px var(--ck-glass-shadow);
}

.ck-pill {
  font-size: 12px;
  font-weight: 900;
  padding: 6px 16px 6px 6px;
  border-radius: 18px 0px 0px 18px;
  line-height: 1;
  position: relative;
  overflow: hidden;
  min-height: 100px;
  /* Kendi üzerinde pozitif bir zikzak kesimi yapan kreatif özellik */
  clip-path: polygon(
    0 0, 
    100% 0, 
    calc(100% - 8px) 8%, 
    100% 16%, 
    calc(100% - 8px) 24%, 
    100% 32%, 
    calc(100% - 8px) 40%, 
    100% 48%, 
    calc(100% - 8px) 56%, 
    100% 64%, 
    calc(100% - 8px) 72%, 
    100% 80%, 
    calc(100% - 8px) 88%, 
    100% 100%, 
    0 100%
  );
}

.ck-pill span {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(270deg);
  transform-origin: center;
  white-space: nowrap;
  text-transform: uppercase;
}

/* Tone mapping */
.ck-pill[data-tone="ready"] { background: var(--blue); color: var(--white-overlay-900); }
.ck-pill[data-tone="running"] { background: var(--yellow-500); color: var(--dark); } /* better contrast for yellow */
.ck-pill[data-tone="paused"] { background: var(--orange-500); color: var(--white-overlay-900); }
.ck-pill[data-tone="finished"] { background: var(--green); color: var(--white-overlay-900); }
.ck-pill[data-tone="rejected"] { background: var(--red); color: var(--white-overlay-900); }

.ck-name {
  font-weight: 900;
  font-size: 14px;
  line-height: 1.2;
  margin-bottom: 10px;
  word-break: break-word;
}

.ck-kv {
  display: grid;
  gap: 10px;
}

.ck-kv-item span {
  display: block;
  font-size: 11px;
  opacity: .65;
  margin-bottom: 3px;
}

.ck-kv-item b {
  display: block;
  font-size: 13px;
  font-weight: 900;
  word-break: break-word;
}

.ck-chevron {
  font-size: 32px;
  opacity: .25;
  line-height: 1;
  transform: translateX(4px);
}

/* Quality Control Status Highlights */
.ck-status-card-qc--running { background: linear-gradient(270deg, var(--ck-success-bg), transparent, transparent); border-radius: 16px; }
.ck-status-card-qc--rejected { background: linear-gradient(270deg, var(--ck-danger-bg), transparent, transparent); border-radius: 16px; }
.ck-status-card-qc--pending { background: linear-gradient(270deg, rgba(59, 130, 246, 0.55), transparent, transparent); border-radius: 16px; }
</style>
