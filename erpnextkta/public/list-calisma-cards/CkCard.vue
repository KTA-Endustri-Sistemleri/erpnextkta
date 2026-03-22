<template>
  <button class="ck-card" @click="$emit('click')">
    <div class="row no-gutters" :class="qcClasses">
      <div class="col-2 p-0 ck-pill" :data-tone="statusTone">
        <span>{{ row.durum || "-" }}</span>
      </div>
      <div class="col-9 py-2 pl-2">
        <div class="ck-name">{{ row.operator }}</div>
        <div class="ck-kv">
          <div class="ck-kv-item">
            <span>Ürün Kodu</span>
            <b>{{ row.urun_kodu || "-" }}</b>
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
  background: var(--card-bg);
  border: 1px solid rgba(0, 0, 0, .08);
  border-radius: 18px;
  padding: 0;
  box-shadow: 0 1px 0 rgba(0, 0, 0, .02);
  margin-bottom: 12px;
  display: block;
}

.ck-card:active {
  transform: scale(.995);
}

.ck-pill {
  font-size: 12px;
  font-weight: 900;
  padding: 6px 10px;
  border-radius: 18px 0px 0px 18px;
  line-height: 1;
  /* border: 1px solid rgba(0, 0, 0, .08); */
  position: relative;
  overflow: hidden;
  min-height: 100px;
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

/* Tone mapping and decorative edges */
.ck-pill[data-tone="ready"] { background: var(--blue); color: var(--white-overlay-900); }
.ck-pill[data-tone="running"] { background: var(--yellow-500); color: var(--white-overlay-900); }
.ck-pill[data-tone="paused"] { background: var(--orange-500); color: var(--white-overlay-900); }
.ck-pill[data-tone="finished"] { background: var(--green); color: var(--white-overlay-900); }
.ck-pill[data-tone="rejected"] { background: var(--red); color: var(--white-overlay-900); }

.ck-pill::after {
  content: "";
  position: absolute;
  top: -1px;
  bottom: -1px;
  right: -1px;
  width: 17px;
  background: var(--card-bg);
  clip-path: polygon(
    100% 0%,
    0% 8%,
    100% 16%,
    0% 24%,
    100% 32%,
    0% 40%,
    100% 48%,
    0% 56%,
    100% 64%,
    0% 72%,
    100% 80%,
    0% 88%,
    100% 100%
  );
}

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
  font-size: 48px;
  opacity: .25;
  line-height: 1;
}

.ck-status-card-qc--running { background: linear-gradient(270deg, var(--green), transparent, transparent); border-radius: 16px; }
.ck-status-card-qc--rejected { background: linear-gradient(270deg, var(--red), transparent, transparent); border-radius: 16px; }
.ck-status-card-qc--pending { background: linear-gradient(270deg, var(--blue), transparent, transparent); border-radius: 16px; }
</style>
