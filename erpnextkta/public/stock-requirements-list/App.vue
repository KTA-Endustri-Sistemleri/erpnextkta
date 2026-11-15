<template>
	<div class="srl-container">
		<!-- FILTERS -->
		<div class="srl-filters">
			<div class="srl-filters-row">
				<div class="srl-filter-group srl-filter-group--item">
					<label>{{ __("Malzeme Kodu") }}</label>
					<div class="srl-link-input" ref="itemLinkRef"></div>
				</div>
				<div class="srl-filter-toggles">
					<label class="srl-toggle">
						<input type="checkbox" v-model="showBomExplosion" />
						<span>{{ __("BOM Patlatma") }}</span>
					</label>
					<label class="srl-toggle">
						<input type="checkbox" v-model="weeklyView" />
						<span>{{ __("Haftalık Görünüm") }}</span>
					</label>
					<label class="srl-toggle">
						<input type="checkbox" v-model="onlyExceptions" />
						<span>{{ __("Sadece İstisnalar") }}</span>
					</label>
				</div>
				<button class="btn btn-primary btn-sm srl-btn-query" @click="fetchData" :disabled="loading">
					<span v-if="loading" class="srl-spinner"></span>
					<span v-else>{{ __("Sorgula") }}</span>
				</button>
			</div>
		</div>

		<!-- LOADING STATE -->
		<div v-if="loading" class="srl-loading">
			<div class="srl-loading-spinner"></div>
			<p>{{ __("Veriler yükleniyor...") }}</p>
		</div>

		<!-- EMPTY STATE -->
		<div v-else-if="!data && !errorMessage" class="srl-empty-state">
			<div class="srl-empty-icon">📋</div>
			<h3>{{ __("Stok İhtiyaç Listesi (MD04)") }}</h3>
			<p>{{ __("Bir malzeme kodu seçerek stok/ihtiyaç analizini başlatın.") }}</p>
		</div>

		<!-- ERROR STATE -->
		<div v-else-if="errorMessage" class="srl-error-state">
			<div class="srl-error-icon">⚠️</div>
			<p>{{ errorMessage }}</p>
		</div>

		<!-- DATA VIEW -->
		<template v-else-if="data">
			<!-- HEADER CARDS -->
			<div class="srl-summary-cards">
				<div class="srl-card" :class="{ 'srl-card--warning': data.item_info.current_stock <= 0 }">
					<div class="srl-card-value">{{ formatQty(data.item_info.current_stock) }}</div>
					<div class="srl-card-label">{{ __("Mevcut Stok") }}</div>
					<div class="srl-card-unit">{{ data.item_info.uom }}</div>
				</div>
				<div class="srl-card">
					<div class="srl-card-value">{{ formatQty(data.item_info.ordered_qty) }}</div>
					<div class="srl-card-label">{{ __("Açık PO") }}</div>
					<div class="srl-card-unit">{{ data.item_info.uom }}</div>
				</div>
				<div class="srl-card">
					<div class="srl-card-value">{{ formatQty(data.summary.total_requirements) }}</div>
					<div class="srl-card-label">{{ __("Toplam Talep") }}</div>
					<div class="srl-card-unit">{{ data.item_info.uom }}</div>
				</div>
				<div class="srl-card" :class="netReqCardClass">
					<div class="srl-card-value">{{ formatQty(data.summary.net_requirement) }}</div>
					<div class="srl-card-label">{{ __("Net İhtiyaç") }}</div>
					<div class="srl-card-badge" v-if="data.summary.net_requirement > 0">{{ __("Eksik") }}</div>
					<div class="srl-card-badge srl-card-badge--ok" v-else>{{ __("Yeterli") }}</div>
				</div>
				<div class="srl-card">
					<div class="srl-card-value">{{ data.summary.coverage_days }}</div>
					<div class="srl-card-label">{{ __("Karşılanma (Gün)") }}</div>
					<div class="srl-card-sub" v-if="data.summary.first_shortage_date">
						{{ __("İlk Açık") }}: {{ formatDate(data.summary.first_shortage_date) }}
					</div>
				</div>
				<div class="srl-card" :class="{ 'srl-card--danger': data.summary.exception_count > 0 }">
					<div class="srl-card-value">{{ data.summary.exception_count }}</div>
					<div class="srl-card-label">{{ __("İstisna") }}</div>
				</div>
			</div>

			<!-- ITEM INFO BAR -->
			<div class="srl-item-info-bar">
				<div class="srl-item-info-main">
					<span class="srl-item-code" @click="openDoc('Item', data.item_info.item_code)">
						{{ data.item_info.item_code }}
					</span>
					<span class="srl-item-name">{{ data.item_info.item_name }}</span>
				</div>
				<div class="srl-item-info-meta">
					<span v-if="data.item_info.item_group" class="srl-meta-tag">{{ data.item_info.item_group }}</span>
					<span v-if="data.item_info.default_supplier" class="srl-meta-tag srl-meta-tag--supplier"
						@click="openDoc('Supplier', data.item_info.default_supplier)">
						🏭 {{ data.item_info.default_supplier }}
					</span>
					<span v-if="data.item_info.lead_time_days" class="srl-meta-tag">
						⏱️ {{ data.item_info.lead_time_days }} {{ __("gün") }}
					</span>
					<span v-if="data.item_info.weekly_production" class="srl-meta-tag">
						⚡ {{ __("Haftalık Kapasite") }}: {{ formatQty(data.item_info.weekly_production) }}
					</span>
					<span v-if="data.item_info.moq" class="srl-meta-tag">
						📦 MOQ: {{ formatQty(data.item_info.moq) }}
					</span>
					<span v-if="data.item_info.reorder_level" class="srl-meta-tag srl-meta-tag--safety">
						🔁 {{ __("Yeniden Sipariş Seviyesi") }}: {{ formatQty(data.item_info.reorder_level) }}
					</span>
					<span v-if="data.item_info.reorder_qty" class="srl-meta-tag">
						🛒 {{ __("Yeniden Sipariş Miktarı") }}: {{ formatQty(data.item_info.reorder_qty) }}
					</span>
					<span v-if="!data.item_info.reorder_level && data.item_info.safety_stock" class="srl-meta-tag srl-meta-tag--safety">
						🛡️ {{ __("Emniyet") }}: {{ formatQty(data.item_info.safety_stock) }}
					</span>
				</div>
			</div>

			<!-- BOM CHILDREN (if explosion enabled) -->
			<div v-if="showBomExplosion && data.bom_children && data.bom_children.length" class="srl-bom-panel">
				<div class="srl-bom-header" @click="bomPanelOpen = !bomPanelOpen">
					<span>📐 {{ __("BOM Bileşenleri") }} ({{ data.bom_children.length }})</span>
					<span class="srl-bom-toggle">{{ bomPanelOpen ? '▼' : '▶' }}</span>
				</div>
				<div v-if="bomPanelOpen" class="srl-bom-list">
					<div v-for="child in data.bom_children" :key="child.item_code" class="srl-bom-item"
						@click="switchItem(child.item_code)">
						<span class="srl-bom-item-code">{{ child.item_code }}</span>
						<span class="srl-bom-item-name">{{ child.item_name }}</span>
						<span class="srl-bom-item-qty">{{ formatQty(child.qty_per_unit) }} {{ child.uom }}</span>
					</div>
				</div>
			</div>

			<!-- ELEMENT TYPE FILTER -->
			<div class="srl-element-filters">
				<label v-for="(label, key) in elementTypeLabels" :key="key" class="srl-element-filter-tag"
					:class="{ 'srl-element-filter-tag--active': activeElementTypes.includes(key) }">
					<input type="checkbox" :value="key" v-model="activeElementTypes" />
					<span class="srl-element-dot" :style="{ background: elementTypeColors[key] }"></span>
					{{ label }}
				</label>
			</div>

			<!-- MRP ELEMENTS TABLE -->
			<div class="srl-table-container">
				<table class="srl-table">
					<thead>
						<tr>
							<th class="srl-th-date">{{ __("Tarih") }}</th>
							<th class="srl-th-type">{{ __("MRP Elem") }}</th>
							<th class="srl-th-label">{{ __("Açıklama") }}</th>
							<th class="srl-th-doc">{{ __("Belge No") }}</th>
							<th class="srl-th-receipt">{{ __("Arz (+)") }}</th>
							<th class="srl-th-req">{{ __("Talep (−)") }}</th>
							<th class="srl-th-balance">{{ __("Bakiye") }}</th>
							<th class="srl-th-exception">⚠</th>
						</tr>
					</thead>
					<tbody>
						<template v-if="!weeklyView">
							<tr v-for="(el, idx) in filteredElements" :key="idx"
								:class="getRowClass(el)"
								@click="onRowClick(el)">
								<td class="srl-td-date">{{ formatDate(el.date) }}</td>
								<td class="srl-td-type">
									<span class="srl-type-badge" :style="{ background: elementTypeColors[el.mrp_element_type] }">
										{{ el.mrp_element_type }}
									</span>
								</td>
								<td class="srl-td-label">{{ el.mrp_element_label }}</td>
								<td class="srl-td-doc">
									<a v-if="el.element_data" @click.stop="openDoc(el.doctype, el.element_data)">
										{{ el.element_data }}
									</a>
								</td>
								<td class="srl-td-receipt">
									<span v-if="el.receipt_qty">{{ formatQty(el.receipt_qty) }}</span>
								</td>
								<td class="srl-td-req">
									<span v-if="el.requirement_qty">{{ formatQty(el.requirement_qty) }}</span>
								</td>
								<td class="srl-td-balance" :class="getBalanceClass(el)">
									{{ formatQty(el.display_available_qty !== undefined ? el.display_available_qty : el.available_qty) }}
								</td>
								<td class="srl-td-exception">
									<span v-if="el.exception_code" class="srl-exception-badge"
										:class="'srl-exception--' + el.exception_code.toLowerCase()"
										:title="el.exception_message">
										{{ getExceptionIcon(el.exception_code) }}
									</span>
								</td>
							</tr>
						</template>
						<template v-else>
							<!-- Açılış / Başlangıç Stoğu -->
							<tr v-if="data && data.stock_element && activeElementTypes.includes('Stock')" class="srl-opening-row">
								<td class="srl-td-date">{{ formatDate(data.stock_element.date) }}</td>
								<td class="srl-td-type">
									<span class="srl-type-badge" :style="{ background: elementTypeColors.Stock }">
										Stock
									</span>
								</td>
								<td class="srl-td-label font-weight-bold">{{ data.stock_element.mrp_element_label }} ({{ __("Açılış Stoğu") }})</td>
								<td class="srl-td-doc">-</td>
								<td class="srl-td-receipt font-weight-bold">{{ formatQty(data.stock_element.receipt_qty) }}</td>
								<td class="srl-td-req">-</td>
								<td class="srl-td-balance font-weight-bold">{{ formatQty(data.stock_element.available_qty) }}</td>
								<td class="srl-td-exception"></td>
							</tr>
							<!-- Emniyet Stoku (varsa) -->
							<tr v-if="data && data.safety_element && activeElementTypes.includes('SafeSt')" class="srl-opening-row srl-opening-row--safety">
								<td class="srl-td-date">{{ formatDate(data.safety_element.date) }}</td>
								<td class="srl-td-type">
									<span class="srl-type-badge" :style="{ background: elementTypeColors.SafeSt }">
										SafeSt
									</span>
								</td>
								<td class="srl-td-label font-weight-bold">{{ data.safety_element.mrp_element_label }}</td>
								<td class="srl-td-doc">-</td>
								<td class="srl-td-receipt">-</td>
								<td class="srl-td-req font-weight-bold">{{ formatQty(data.safety_element.requirement_qty) }}</td>
								<td class="srl-td-balance font-weight-bold" :class="getBalanceClass(data.safety_element)">
									{{ formatQty(data.safety_element.available_qty) }}
								</td>
								<td class="srl-td-exception"></td>
							</tr>

							<template v-for="(wk, wIdx) in filteredWeeklyElements" :key="wIdx">
								<tr class="srl-week-header" @click="toggleWeek(wk.week_label)">
									<td colspan="4">
										<span class="srl-week-toggle">{{ expandedWeeks.includes(wk.week_label) ? '▼' : '▶' }}</span>
										<strong>{{ wk.week_label }}</strong>
										<span class="srl-week-count">({{ wk.element_count }} {{ __("hareket") }})</span>
									</td>
									<td class="srl-td-receipt">
										<span v-if="wk.receipt_qty">{{ formatQty(wk.receipt_qty) }}</span>
									</td>
									<td class="srl-td-req">
										<span v-if="wk.requirement_qty">{{ formatQty(wk.requirement_qty) }}</span>
									</td>
									<td class="srl-td-balance" :class="{ 'srl-balance-negative': wk.available_qty < 0 }">
										{{ formatQty(wk.available_qty) }}
									</td>
									<td></td>
								</tr>
								<template v-if="expandedWeeks.includes(wk.week_label)">
									<tr v-for="(el, elIdx) in getWeekFilteredElements(wk)" :key="wIdx + '-' + elIdx"
										:class="getRowClass(el)"
										@click="onRowClick(el)"
										class="srl-week-child-row">
										<td class="srl-td-date">{{ formatDate(el.date) }}</td>
										<td class="srl-td-type">
											<span class="srl-type-badge" :style="{ background: elementTypeColors[el.mrp_element_type] }">
												{{ el.mrp_element_type }}
											</span>
										</td>
										<td class="srl-td-label">{{ el.mrp_element_label }}</td>
										<td class="srl-td-doc">
											<a v-if="el.element_data" @click.stop="openDoc(el.doctype, el.element_data)">
												{{ el.element_data }}
											</a>
										</td>
										<td class="srl-td-receipt">
											<span v-if="el.receipt_qty">{{ formatQty(el.receipt_qty) }}</span>
										</td>
										<td class="srl-td-req">
											<span v-if="el.requirement_qty">{{ formatQty(el.requirement_qty) }}</span>
										</td>
										<td class="srl-td-balance" :class="getBalanceClass(el)">
											{{ formatQty(el.display_available_qty !== undefined ? el.display_available_qty : el.available_qty) }}
										</td>
										<td class="srl-td-exception">
											<span v-if="el.exception_code" class="srl-exception-badge"
												:class="'srl-exception--' + el.exception_code.toLowerCase()"
												:title="el.exception_message">
												{{ getExceptionIcon(el.exception_code) }}
											</span>
										</td>
									</tr>
								</template>
							</template>
						</template>
					</tbody>
				</table>
				<div v-if="filteredElements.length === 0 && !weeklyView" class="srl-no-data">
					{{ __("Gösterilecek MRP elementi bulunamadı.") }}
				</div>
			</div>

			<!-- CHART -->
			<div class="srl-chart-section">
				<h4 class="srl-chart-title">{{ __("Stok Evrimi") }}</h4>
				<div ref="chartRef" class="srl-chart"></div>
			</div>
		</template>

		<!-- PURCHASE PROPOSAL (PO) MODAL -->
		<div v-if="poModalOpen" class="srl-modal-backdrop" @click.self="poModalOpen = false">
			<div class="srl-modal-container">
				<div class="srl-modal-header">
					<div class="srl-modal-title-group">
						<span class="srl-modal-badge">PurRqs</span>
						<h3 class="srl-modal-title">{{ __("Planlı Satın Alma Siparişi Aç") }}</h3>
					</div>
					<button class="srl-modal-close-btn" @click="poModalOpen = false">✕</button>
				</div>

				<div class="srl-modal-body" v-if="poModalEl">
					<!-- Material & Requirement Summary -->
					<div class="srl-modal-info-box">
						<div class="srl-modal-info-row">
							<span>{{ __("Malzeme") }}:</span>
							<strong>{{ itemCode }} - {{ data?.item_info?.item_name }}</strong>
						</div>
						<div class="srl-modal-info-row">
							<span>{{ __("İhtiyaç Tarihi") }}:</span>
							<strong>{{ formatDate(poModalEl.date) }} ({{ poModalEl.week_label }})</strong>
						</div>
						<div class="srl-modal-info-row">
							<span>{{ __("Net Açık") }}:</span>
							<strong class="srl-text-danger">{{ formatQty(poModalEl.deficit_qty || poModalEl.receipt_qty) }} {{ data?.item_info?.uom }}</strong>
						</div>
					</div>

					<!-- Supplier Selection -->
					<div class="srl-modal-section-title">
						{{ __("Tedarikçi Seçimi") }}
						<span class="srl-section-sub">({{ __("Aktif Item Price kayıtları listelenmektedir") }})</span>
					</div>

					<div class="srl-supplier-list">
						<div
							v-for="supp in supplierListWithStats"
							:key="supp.supplier"
							class="srl-supplier-card"
							:class="{ 'srl-supplier-card--selected': poSelectedSupplier === supp.supplier }"
							@click="poSelectedSupplier = supp.supplier">
							<div class="srl-supplier-header">
								<div class="srl-supplier-radio-wrap">
									<input
										type="radio"
										name="po_supplier"
										:value="supp.supplier"
										v-model="poSelectedSupplier" />
									<span class="srl-supplier-name">{{ supp.supplier }}</span>
								</div>
								<div class="srl-supplier-badges">
									<span v-if="supp.is_default" class="srl-badge srl-badge--default">
										{{ __("Varsayılan") }}
									</span>
									<span v-if="supp.savingsPercent > 0" class="srl-badge srl-badge--savings">
										💡 %{{ supp.savingsPercent }} {{ __("Daha Ucuz") }}
									</span>
								</div>
							</div>

							<div class="srl-supplier-details">
								<div class="srl-supp-col">
									<span class="srl-detail-label">{{ __("Birim Fiyat") }}</span>
									<span class="srl-detail-val">{{ supp.rate ? supp.rate + ' ' + supp.currency : __('Fiyat Yok') }}</span>
								</div>
								<div class="srl-supp-col">
									<span class="srl-detail-label">{{ __("MOQ / Paket") }}</span>
									<span class="srl-detail-val">{{ formatQty(supp.moq) }} / {{ formatQty(supp.paket) }}</span>
								</div>
								<div class="srl-supp-col">
									<span class="srl-detail-label">{{ __("Temin Süresi") }}</span>
									<span class="srl-detail-val">{{ supp.lead_time_days }} {{ __("gün") }}</span>
								</div>
								<div class="srl-supp-col srl-supp-col--highlight">
									<span class="srl-detail-label">{{ __("Sipariş Miktarı") }}</span>
									<span class="srl-detail-val srl-text-primary">{{ formatQty(supp.calcQty) }} {{ data?.item_info?.uom }}</span>
								</div>
							</div>
						</div>
					</div>

					<!-- Delivery Date Input -->
					<div class="srl-modal-form-group">
						<label>{{ __("İstenen Teslim Tarihi") }}</label>
						<input type="date" class="form-control" v-model="poDeliveryDate" />
					</div>
				</div>

				<div class="srl-modal-footer">
					<div class="srl-modal-summary-text" v-if="selectedSupplierObj">
						<span>{{ __("Sipariş Verilecek") }}:</span>
						<strong>{{ formatQty(calculatedPoQty) }} {{ data?.item_info?.uom }}</strong>
						<span v-if="selectedSupplierObj.rate">
							(~{{ formatQty(calculatedPoQty * selectedSupplierObj.rate) }} {{ selectedSupplierObj.currency }})
						</span>
					</div>
					<div class="srl-modal-actions">
						<button class="btn btn-default btn-sm" @click="poModalOpen = false">{{ __("İptal") }}</button>
						<button class="btn btn-primary btn-sm srl-btn-create-po" @click="confirmCreatePo">
							🚀 {{ __("Satın Alma Siparişi Aç") }}
						</button>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from "vue";

const __ = (...args) => window.__(...args);

// Refs
const itemLinkRef = ref(null);
const chartRef = ref(null);

// State
const itemCode = ref("");
const showBomExplosion = ref(false);
const weeklyView = ref(false);
const onlyExceptions = ref(false);
const loading = ref(false);
const errorMessage = ref("");
const data = ref(null);
const bomPanelOpen = ref(false);
const expandedWeeks = ref([]);
let chartInstance = null;

const ALL_ELEMENT_TYPES = [
	"Stock",
	"SafeSt",
	"CustOrd",
	"PO",
	"InTrnst",
	"Bonded",
	"PrdOrd",
	"PldOrd",
	"PurRqs",
	"DepReq",
	"SimReq",
	"MR-Mfg",
	"MR-Pur",
];

const elementTypeLabels = computed(() => ({
	Stock: __("Mevcut Stok"),
	SafeSt: __("Emniyet Stoku"),
	CustOrd: __("Müşteri Siparişi"),
	PO: __("Satın Alma Siparişi"),
	InTrnst: __("Yolda"),
	Bonded: __("Antrepoda"),
	PrdOrd: __("İş Emri (Üretim)"),
	PldOrd: __("Planlı Sipariş (Öneri)"),
	PurRqs: __("Planlı Satın Alma Siparişi"),
	DepReq: __("Bağımlı İhtiyaç"),
	SimReq: __("Planlı Bağımlı İhtiyaç"),
	"MR-Mfg": __("Üretim Talebi"),
	"MR-Pur": __("Satın Alma Talebi"),
}));

const elementTypeColors = {
	Stock: "#6c757d",
	SafeSt: "#b45309",
	CustOrd: "#e74c3c",
	PO: "#27ae60",
	InTrnst: "#0ea5e9",
	Bonded: "#8b5cf6",
	PrdOrd: "#2980b9",
	PldOrd: "#0284c7",
	PurRqs: "#10b981",
	DepReq: "#e67e22",
	SimReq: "#c2410c",
	"MR-Mfg": "#8e44ad",
	"MR-Pur": "#16a085",
};

const activeElementTypes = ref([...ALL_ELEMENT_TYPES]);

// Computed
const filteredElements = computed(() => {
	if (!data.value || !data.value.mrp_elements) return [];
	let els = data.value.mrp_elements;
	if (onlyExceptions.value) {
		els = els.filter((e) => e.exception_code);
	}
	els = els.filter((e) => activeElementTypes.value.includes(e.mrp_element_type));

	// Dinamik bakiye akışı: aktif filtrelere göre bakiye yeniden hesaplanır
	let running = 0;
	return els.map((el) => {
		const r = parseFloat(el.receipt_qty) || 0;
		const q = parseFloat(el.requirement_qty) || 0;
		running += r - q;
		return {
			...el,
			display_available_qty: running,
		};
	});
});

const filteredWeeklyElements = computed(() => {
	if (!data.value || !data.value.mrp_elements) return [];

	const isStockActive = activeElementTypes.value.includes("Stock");
	const isSafeStActive = activeElementTypes.value.includes("SafeSt");

	let running = 0;
	if (isStockActive && data.value.stock_element) {
		running += parseFloat(data.value.stock_element.receipt_qty) || 0;
	}
	if (isSafeStActive && data.value.safety_element) {
		running -= parseFloat(data.value.safety_element.requirement_qty) || 0;
	}

	return data.value.mrp_elements
		.map((wk) => {
			let childEls = (wk.elements || []).filter((e) => {
				if (onlyExceptions.value && !e.exception_code) return false;
				return activeElementTypes.value.includes(e.mrp_element_type);
			});

			let weekReceipt = 0;
			let weekReq = 0;

			let childRunning = running;
			const mappedChildEls = childEls.map((e) => {
				const r = parseFloat(e.receipt_qty) || 0;
				const q = parseFloat(e.requirement_qty) || 0;
				childRunning += r - q;
				weekReceipt += r;
				weekReq += q;
				return {
					...e,
					display_available_qty: childRunning,
				};
			});

			running = childRunning;

			return {
				...wk,
				filtered_elements: mappedChildEls,
				element_count: mappedChildEls.length,
				receipt_qty: weekReceipt,
				requirement_qty: weekReq,
				available_qty: running,
			};
		})
		.filter((wk) => wk.element_count > 0);
});

const netReqCardClass = computed(() => {
	if (!data.value) return "";
	return data.value.summary.net_requirement > 0 ? "srl-card--danger" : "srl-card--success";
});

// Methods
function fetchData() {
	if (!itemCode.value) {
		frappe.show_alert({ message: __("Malzeme kodu seçiniz"), indicator: "orange" });
		return;
	}
	loading.value = true;
	errorMessage.value = "";
	data.value = null;

	frappe.call({
		method: "erpnextkta.kta_mrp.api_impl.stock_requirements_list.get_stock_requirements",
		args: {
			item_code: itemCode.value,
			show_bom_explosion: showBomExplosion.value ? 1 : 0,
			weekly_view: weeklyView.value ? 1 : 0,
		},
		callback(r) {
			loading.value = false;
			if (r.message) {
				data.value = r.message;
				nextTick(() => renderChart());
			}
		},
		error() {
			loading.value = false;
			errorMessage.value = __("Veri yüklenirken bir hata oluştu.");
		},
	});
}

function switchItem(newItemCode) {
	itemCode.value = newItemCode;
	if (itemLinkControl) {
		itemLinkControl.set_value(newItemCode);
	}
	fetchData();
}

function openDoc(doctype, name) {
	if (doctype && name) {
		frappe.set_route("Form", doctype, name);
	}
}

// PO Proposal Modal State
const poModalOpen = ref(false);
const poModalEl = ref(null);
const poSelectedSupplier = ref("");
const poDeliveryDate = ref("");

function onRowClick(el) {
	if (el.mrp_element_type === "PldOrd") {
		createWorkOrder(el);
		return;
	}
	if (el.mrp_element_type === "PurRqs") {
		openPurchaseProposalModal(el);
		return;
	}
	if (el.doctype && el.element_data) {
		openDoc(el.doctype, el.element_data);
	}
}

function openPurchaseProposalModal(el) {
	poModalEl.value = el;
	poDeliveryDate.value = el.date;
	const suppliers = el.suppliers_data || [];
	const defaultSupp = suppliers.find((s) => s.is_default) || suppliers[0];
	poSelectedSupplier.value = defaultSupp ? defaultSupp.supplier : (el.element_data || "");
	poModalOpen.value = true;
}

const supplierListWithStats = computed(() => {
	if (!poModalEl.value || !poModalEl.value.suppliers_data) return [];
	const deficit = parseFloat(poModalEl.value.deficit_qty) || parseFloat(poModalEl.value.receipt_qty) || 1;
	const suppliers = poModalEl.value.suppliers_data;

	const defaultSupp = suppliers.find((s) => s.is_default) || suppliers[0];
	const baselineRate = defaultSupp ? parseFloat(defaultSupp.rate) : 0;

	return suppliers.map((s) => {
		const moq = parseFloat(s.moq) || 1;
		const paket = parseFloat(s.paket) || 1;
		const calcQty = Math.max(moq, Math.ceil(deficit / paket) * paket);
		const rate = parseFloat(s.rate) || 0;
		const totalCost = calcQty * rate;

		let savingsPercent = 0;
		if (baselineRate > 0 && rate > 0 && rate < baselineRate) {
			savingsPercent = Math.round(((baselineRate - rate) / baselineRate) * 100);
		}

		return {
			...s,
			calcQty,
			totalCost,
			savingsPercent,
		};
	});
});

const selectedSupplierObj = computed(() => {
	if (!supplierListWithStats.value.length) return null;
	return supplierListWithStats.value.find((s) => s.supplier === poSelectedSupplier.value) || supplierListWithStats.value[0];
});

const calculatedPoQty = computed(() => {
	if (selectedSupplierObj.value) {
		return selectedSupplierObj.value.calcQty;
	}
	return parseFloat(poModalEl.value?.receipt_qty) || 1;
});

function confirmCreatePo() {
	if (!poModalEl.value || !poSelectedSupplier.value) return;
	const el = poModalEl.value;
	const currentItem = itemCode.value || (data.value && data.value.item_info && data.value.item_info.item_code);
	const supplier = poSelectedSupplier.value;
	const qty = calculatedPoQty.value;
	const deliveryDate = poDeliveryDate.value || el.date;
	const warehouse = el.default_warehouse || (data.value && data.value.item_info && data.value.item_info.default_warehouse) || undefined;

	const fields = {
		supplier: supplier,
		schedule_date: deliveryDate,
		items: [
			{
				item_code: currentItem,
				qty: qty,
				schedule_date: deliveryDate,
			},
		],
	};
	if (warehouse) {
		fields.set_warehouse = warehouse;
		fields.items[0].warehouse = warehouse;
	}

	poModalOpen.value = false;
	frappe.new_doc("Purchase Order", fields);
}

function createWorkOrder(el) {
	const currentItem = itemCode.value || (data.value && data.value.item_info && data.value.item_info.item_code);
	const qtyFormatted = formatQty(el.receipt_qty) || "1";
	const itemEscaped = frappe.utils.escape_html(currentItem || "");
	const confirmMsg = `${__("Bu planlı sipariş için İş Emri açmak istiyor musunuz?")}<br><br><b>${__("Ürün")}:</b> ${itemEscaped}<br><b>${__("Miktar")}:</b> ${qtyFormatted}`;

	frappe.confirm(confirmMsg, () => {
		const salesOrder = (el.doctype === "Sales Order" && el.element_data && el.element_data !== currentItem)
			? el.element_data
			: undefined;

		const startDate = el.start_date || el.date;
		const endDate = el.date;
		const plannedStart = startDate ? (startDate.includes(" ") ? startDate : `${startDate} 08:00:00`) : undefined;
		const plannedEnd = endDate ? (endDate.includes(" ") ? endDate : `${endDate} 17:00:00`) : undefined;

		const fields = {
			production_item: currentItem,
			qty: parseFloat(el.receipt_qty) || 1,
		};
		if (plannedStart) fields.planned_start_date = plannedStart;
		if (plannedEnd) fields.planned_end_date = plannedEnd;
		if (salesOrder) fields.sales_order = salesOrder;

		frappe.new_doc("Work Order", fields);
	});
}

function toggleWeek(weekLabel) {
	const idx = expandedWeeks.value.indexOf(weekLabel);
	if (idx >= 0) {
		expandedWeeks.value.splice(idx, 1);
	} else {
		expandedWeeks.value.push(weekLabel);
	}
}

function getWeekFilteredElements(wk) {
	return wk.filtered_elements || [];
}

function formatQty(val) {
	if (val === null || val === undefined) return "";
	const num = parseFloat(val);
	if (isNaN(num)) return "";
	return num.toLocaleString("tr-TR", {
		minimumFractionDigits: num % 1 === 0 ? 0 : 2,
		maximumFractionDigits: 2,
	});
}

function formatDate(dateStr) {
	if (!dateStr) return "";
	const d = new Date(dateStr);
	return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function getRowClass(el) {
	const classes = ["srl-row"];
	if (el.exception_code === "SHORTAGE") classes.push("srl-row--shortage");
	else if (el.exception_code === "BELOW_SAFETY") classes.push("srl-row--warning");
	else if (el.exception_code === "OVERDUE") classes.push("srl-row--overdue");
	if (el.mrp_element_type === "Stock") classes.push("srl-row--stock");
	if (el.element_data) classes.push("srl-row--clickable");
	return classes;
}

function getBalanceClass(el) {
	// Bakiye emniyet stoku düşülmüş net miktardır
	const safety = data.value ? data.value.item_info.safety_stock || 0 : 0;
	const qty = el.display_available_qty !== undefined ? el.display_available_qty : el.available_qty;
	if (qty < -safety) return "srl-balance-negative";
	if (qty < 0) return "srl-balance-warning";
	return "srl-balance-ok";
}

function getExceptionIcon(code) {
	const icons = {
		SHORTAGE: "🔴",
		BELOW_SAFETY: "🟡",
		OVERDUE: "🟠",
		EXCESS: "🔵",
		RESCHEDULE_IN: "⏪",
		RESCHEDULE_OUT: "⏩",
	};
	return icons[code] || "⚠️";
}

function renderChart() {
	if (!chartRef.value || !data.value) return;

	if (chartInstance) {
		chartInstance.destroy?.();
		chartInstance = null;
	}

	const safety = parseFloat(data.value.item_info?.safety_stock || 0);
	let labels = [];
	let balanceValues = [];
	let reqValues = [];
	let receiptValues = [];

	if (weeklyView.value && filteredWeeklyElements.value.length) {
		const wks = filteredWeeklyElements.value;
		labels = wks.map((w) => w.week_label);
		balanceValues = wks.map((w) => (parseFloat(w.available_qty) || 0) + safety);
		reqValues = wks.map((w) => parseFloat(w.requirement_qty) || 0);
		receiptValues = wks.map((w) => parseFloat(w.receipt_qty) || 0);
	} else if (filteredElements.value.length) {
		const weekData = {};
		filteredElements.value.forEach((el) => {
			if (el.mrp_element_type === "SafeSt") return;
			const w = el.week_label;
			if (!w) return;
			if (!weekData[w]) {
				weekData[w] = { receipt: 0, req: 0, balance: 0 };
			}
			const bal = el.display_available_qty !== undefined ? el.display_available_qty : el.available_qty;
			weekData[w].balance = (parseFloat(bal) || 0) + safety;
			if (el.mrp_element_type === "Stock") return;
			weekData[w].receipt += parseFloat(el.receipt_qty) || 0;
			weekData[w].req += parseFloat(el.requirement_qty) || 0;
		});

		labels = Object.keys(weekData).sort();
		balanceValues = labels.map((w) => weekData[w].balance);
		reqValues = labels.map((w) => weekData[w].req);
		receiptValues = labels.map((w) => weekData[w].receipt);
	} else if (data.value.chart_data && data.value.chart_data.labels) {
		const cd = data.value.chart_data;
		labels = cd.labels;
		const dsMap = {};
		cd.datasets.forEach((ds) => {
			dsMap[ds.name] = ds.values;
		});
		balanceValues = dsMap[__("Kümülatif Stok")] || [];
		reqValues = dsMap[__("Haftalık Talep")] || [];
		receiptValues = dsMap[__("Haftalık Arz")] || [];
	}

	if (!labels.length) return;

	chartInstance = new frappe.Chart(chartRef.value, {
		data: {
			labels: labels,
			datasets: [
				{
					name: __("Kümülatif Stok"),
					values: balanceValues,
					chartType: "line",
				},
				{
					name: __("Haftalık Talep"),
					values: reqValues,
					chartType: "bar",
				},
				{
					name: __("Haftalık Arz"),
					values: receiptValues,
					chartType: "bar",
				},
				{
					name: __("Emniyet Stoku"),
					values: labels.map(() => safety),
					chartType: "line",
				},
			],
		},
		type: "axis-mixed",
		height: 280,
		colors: ["#3498db", "#e74c3c", "#27ae60", "#f39c12"],
		axisOptions: {
			xIsSeries: true,
		},
		tooltipOptions: {
			formatTooltipY: (d) => formatQty(d),
		},
	});
}

// Frappe controls
let itemLinkControl = null;

onMounted(() => {
	// Item Link
	itemLinkControl = frappe.ui.form.make_control({
		df: {
			fieldtype: "Link",
			options: "Item",
			fieldname: "item_code",
			placeholder: __("Malzeme kodu girin..."),
		},
		parent: itemLinkRef.value,
		render_input: true,
	});
	itemLinkControl.$input.on("change", () => {
		itemCode.value = itemLinkControl.get_value();
	});
	itemLinkControl.$input.on("awesomplete-selectcomplete", () => {
		itemCode.value = itemLinkControl.get_value();
	});

	// URL'den item_code parametresi al
	const urlParams = new URLSearchParams(window.location.search);
	const urlItem = urlParams.get("item_code");
	if (urlItem) {
		itemCode.value = urlItem;
		itemLinkControl.set_value(urlItem);
		nextTick(() => fetchData());
	}
});

// Weekly view değiştiğinde tekrar fetch
watch(weeklyView, () => {
	if (data.value) fetchData();
});

// Filtreler değiştiğinde grafiği dinamik güncelle
watch(
	[activeElementTypes, onlyExceptions],
	() => {
		nextTick(() => renderChart());
	},
	{ deep: true }
);
</script>

<style scoped>
/* ===== CONTAINER ===== */
.srl-container {
	font-family: var(--font-stack, -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif);
	color: var(--text-color, #1a1a2e);
	max-width: 100%;
	padding: 0;
}

/* ===== FILTERS ===== */
.srl-filters {
	background: var(--card-bg, #ffffff);
	border: 1px solid var(--border-color, #e2e8f0);
	border-radius: 10px;
	padding: 16px 20px;
	margin-bottom: 16px;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.srl-filters-row {
	display: flex;
	align-items: flex-end;
	gap: 16px;
	flex-wrap: wrap;
}

.srl-filter-group {
	display: flex;
	flex-direction: column;
	gap: 4px;
	min-width: 160px;
}

.srl-filter-group--item {
	min-width: 240px;
	flex: 1;
}

.srl-filter-group label {
	font-size: 11px;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.5px;
	color: var(--text-muted, #6b7280);
}

.srl-filter-toggles {
	display: flex;
	align-items: center;
	gap: 14px;
	flex-wrap: wrap;
}

.srl-toggle {
	display: flex;
	align-items: center;
	gap: 5px;
	font-size: 12px;
	cursor: pointer;
	user-select: none;
	color: var(--text-muted, #6b7280);
}

.srl-toggle input {
	accent-color: var(--primary-color, #5e64ff);
}

.srl-btn-query {
	height: 32px;
	min-width: 100px;
	font-weight: 600;
	border-radius: 6px;
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 6px;
}

.srl-spinner {
	width: 14px;
	height: 14px;
	border: 2px solid rgba(255, 255, 255, 0.3);
	border-top-color: #fff;
	border-radius: 50%;
	animation: srl-spin 0.6s linear infinite;
}

@keyframes srl-spin {
	to { transform: rotate(360deg); }
}

/* ===== LOADING ===== */
.srl-loading {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 60px 20px;
	color: var(--text-muted, #6b7280);
}

.srl-loading-spinner {
	width: 40px;
	height: 40px;
	border: 3px solid var(--border-color, #e2e8f0);
	border-top-color: var(--primary-color, #5e64ff);
	border-radius: 50%;
	animation: srl-spin 0.8s linear infinite;
	margin-bottom: 12px;
}

/* ===== EMPTY / ERROR ===== */
.srl-empty-state,
.srl-error-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 60px 20px;
	color: var(--text-muted, #6b7280);
}

.srl-empty-icon,
.srl-error-icon {
	font-size: 48px;
	margin-bottom: 12px;
}

.srl-empty-state h3 {
	margin: 0 0 8px;
	color: var(--heading-color, #1a1a2e);
}

/* ===== SUMMARY CARDS ===== */
.srl-summary-cards {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
	gap: 12px;
	margin-bottom: 16px;
}

.srl-card {
	background: var(--card-bg, #ffffff);
	border: 1px solid var(--border-color, #e2e8f0);
	border-radius: 10px;
	padding: 16px;
	text-align: center;
	transition: all 0.2s ease;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.srl-card:hover {
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
	transform: translateY(-1px);
}

.srl-card--danger {
	border-color: #e74c3c;
	background: linear-gradient(135deg, #fff5f5, #ffffff);
}

.srl-card--warning {
	border-color: #f39c12;
	background: linear-gradient(135deg, #fffbeb, #ffffff);
}

.srl-card--success {
	border-color: #27ae60;
	background: linear-gradient(135deg, #f0fdf4, #ffffff);
}

.srl-card-value {
	font-size: 22px;
	font-weight: 700;
	color: var(--heading-color, #1a1a2e);
	line-height: 1.2;
}

.srl-card--danger .srl-card-value { color: #e74c3c; }
.srl-card--warning .srl-card-value { color: #f39c12; }
.srl-card--success .srl-card-value { color: #27ae60; }

.srl-card-label {
	font-size: 11px;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.5px;
	color: var(--text-muted, #6b7280);
	margin-top: 4px;
}

.srl-card-unit {
	font-size: 11px;
	color: var(--text-light, #9ca3af);
}

.srl-card-badge {
	display: inline-block;
	font-size: 10px;
	font-weight: 700;
	padding: 2px 8px;
	border-radius: 10px;
	margin-top: 4px;
	background: #e74c3c;
	color: #fff;
}

.srl-card-badge--ok {
	background: #27ae60;
}

.srl-card-sub {
	font-size: 10px;
	color: var(--text-muted, #6b7280);
	margin-top: 2px;
}

/* ===== ITEM INFO BAR ===== */
.srl-item-info-bar {
	background: var(--card-bg, #ffffff);
	border: 1px solid var(--border-color, #e2e8f0);
	border-radius: 10px;
	padding: 12px 20px;
	margin-bottom: 12px;
	display: flex;
	justify-content: space-between;
	align-items: center;
	flex-wrap: wrap;
	gap: 8px;
}

.srl-item-info-main {
	display: flex;
	align-items: center;
	gap: 10px;
}

.srl-item-code {
	font-weight: 700;
	font-size: 15px;
	color: var(--primary-color, #5e64ff);
	cursor: pointer;
}

.srl-item-code:hover { text-decoration: underline; }

.srl-item-name {
	color: var(--text-muted, #6b7280);
	font-size: 13px;
}

.srl-item-info-meta {
	display: flex;
	align-items: center;
	gap: 8px;
	flex-wrap: wrap;
}

.srl-meta-tag {
	font-size: 11px;
	padding: 3px 10px;
	border-radius: 12px;
	background: var(--bg-color, #f1f5f9);
	color: var(--text-muted, #6b7280);
	white-space: nowrap;
}

.srl-meta-tag--supplier {
	cursor: pointer;
	background: #e8f4fd;
	color: #2980b9;
}

.srl-meta-tag--supplier:hover { background: #d4ecfb; }

.srl-meta-tag--safety {
	background: #fef3c7;
	color: #92400e;
}

/* ===== BOM PANEL ===== */
.srl-bom-panel {
	background: var(--card-bg, #ffffff);
	border: 1px solid var(--border-color, #e2e8f0);
	border-radius: 10px;
	margin-bottom: 12px;
	overflow: hidden;
}

.srl-bom-header {
	padding: 10px 20px;
	background: #f8fafc;
	cursor: pointer;
	display: flex;
	justify-content: space-between;
	align-items: center;
	font-weight: 600;
	font-size: 13px;
}

.srl-bom-header:hover { background: #f1f5f9; }

.srl-bom-list {
	padding: 8px 12px;
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
	gap: 6px;
}

.srl-bom-item {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 6px 10px;
	border-radius: 6px;
	cursor: pointer;
	font-size: 12px;
	transition: background 0.15s;
}

.srl-bom-item:hover { background: #e8f4fd; }

.srl-bom-item-code {
	font-weight: 600;
	color: var(--primary-color, #5e64ff);
	min-width: 100px;
}

.srl-bom-item-name {
	flex: 1;
	color: var(--text-muted, #6b7280);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.srl-bom-item-qty {
	font-weight: 600;
	color: var(--text-color, #1a1a2e);
	white-space: nowrap;
}

/* ===== ELEMENT TYPE FILTERS ===== */
.srl-element-filters {
	display: flex;
	gap: 8px;
	flex-wrap: wrap;
	margin-bottom: 12px;
	padding: 0 4px;
}

.srl-element-filter-tag {
	display: flex;
	align-items: center;
	gap: 5px;
	font-size: 11px;
	padding: 4px 10px;
	border-radius: 14px;
	cursor: pointer;
	user-select: none;
	background: var(--bg-color, #f1f5f9);
	color: var(--text-muted, #6b7280);
	transition: all 0.15s;
	border: 1px solid transparent;
}

.srl-element-filter-tag input { display: none; }

.srl-element-filter-tag--active {
	background: var(--card-bg, #ffffff);
	border-color: var(--border-color, #e2e8f0);
	color: var(--text-color, #1a1a2e);
	font-weight: 600;
	box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.srl-element-dot {
	width: 8px;
	height: 8px;
	border-radius: 50%;
	flex-shrink: 0;
}

/* ===== TABLE ===== */
.srl-table-container {
	background: var(--card-bg, #ffffff);
	border: 1px solid var(--border-color, #e2e8f0);
	border-radius: 10px;
	overflow: hidden;
	margin-bottom: 16px;
}

.srl-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 12.5px;
}

.srl-table thead {
	background: #f8fafc;
	position: sticky;
	top: 0;
	z-index: 1;
}

.srl-table th {
	padding: 10px 12px;
	text-align: left;
	font-weight: 700;
	font-size: 11px;
	text-transform: uppercase;
	letter-spacing: 0.3px;
	color: var(--text-muted, #6b7280);
	border-bottom: 2px solid var(--border-color, #e2e8f0);
	white-space: nowrap;
}

.srl-th-receipt,
.srl-th-req,
.srl-th-balance {
	text-align: right;
}

.srl-th-exception {
	text-align: center;
	width: 36px;
}

.srl-table td {
	padding: 8px 12px;
	border-bottom: 1px solid #f1f5f9;
	vertical-align: middle;
}

.srl-td-receipt,
.srl-td-req,
.srl-td-balance {
	text-align: right;
	font-variant-numeric: tabular-nums;
	font-weight: 500;
}

.srl-td-exception {
	text-align: center;
	width: 36px;
}

.srl-td-doc a {
	color: var(--primary-color, #5e64ff);
	cursor: pointer;
	font-weight: 500;
}

.srl-td-doc a:hover {
	text-decoration: underline;
}

/* Row states */
.srl-row {
	transition: background 0.15s;
}

.srl-row--clickable {
	cursor: pointer;
}

.srl-row--clickable:hover {
	background: #f8fafc !important;
}

.srl-row--stock {
	background: #f8fafc;
	font-weight: 600;
}

.srl-row--shortage {
	background: #fff5f5 !important;
}

.srl-row--shortage:hover {
	background: #ffe8e8 !important;
}

.srl-row--warning {
	background: #fffbeb !important;
}

.srl-row--warning:hover {
	background: #fef3c7 !important;
}

.srl-row--overdue {
	background: #fff7ed !important;
}

/* Balance colors */
.srl-balance-negative {
	color: #e74c3c !important;
	font-weight: 700 !important;
}

.srl-balance-warning {
	color: #f39c12 !important;
	font-weight: 600;
}

.srl-balance-ok {
	color: var(--text-color, #1a1a2e);
}

/* Type badge */
.srl-type-badge {
	display: inline-block;
	font-size: 10px;
	font-weight: 700;
	padding: 2px 8px;
	border-radius: 10px;
	color: #fff;
	letter-spacing: 0.3px;
	white-space: nowrap;
}

/* Exception badges */
.srl-exception-badge {
	font-size: 14px;
	cursor: help;
}

/* Weekly view */
.srl-opening-row {
	background: #f8fafc !important;
	border-bottom: 2px solid #cbd5e1;
}

.srl-opening-row td {
	padding: 10px 12px;
}

.srl-opening-row--safety {
	background: #fffbeb !important;
	border-bottom: 2px solid #fde68a;
}

.srl-week-header {
	background: #f1f5f9 !important;
	cursor: pointer;
	font-size: 13px;
}

.srl-week-header:hover {
	background: #e2e8f0 !important;
}

.srl-week-header td {
	padding: 10px 12px;
	font-weight: 600;
}

.srl-week-toggle {
	display: inline-block;
	width: 18px;
	font-size: 10px;
	color: var(--text-muted, #6b7280);
}

.srl-week-count {
	font-weight: 400;
	color: var(--text-muted, #6b7280);
	font-size: 11px;
	margin-left: 6px;
}

.srl-week-child-row {
	border-left: 3px solid var(--primary-color, #5e64ff);
}

.srl-no-data {
	padding: 30px;
	text-align: center;
	color: var(--text-muted, #6b7280);
}

/* ===== CHART ===== */
.srl-chart-section {
	background: var(--card-bg, #ffffff);
	border: 1px solid var(--border-color, #e2e8f0);
	border-radius: 10px;
	padding: 20px;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.srl-chart-title {
	margin: 0 0 12px;
	font-size: 14px;
	font-weight: 700;
	color: var(--heading-color, #1a1a2e);
}

.srl-chart {
	min-height: 280px;
}

/* ===== FRAPPE CONTROL OVERRIDES ===== */
.srl-link-input :deep(.frappe-control),
.srl-date-input :deep(.frappe-control) {
	margin: 0 !important;
}

.srl-link-input :deep(.form-group),
.srl-date-input :deep(.form-group) {
	margin-bottom: 0 !important;
}

.srl-link-input :deep(.control-input),
.srl-date-input :deep(.control-input) {
	display: flex !important;
}

.srl-link-input :deep(input),
.srl-date-input :deep(input) {
	border-radius: 6px !important;
	font-size: 13px !important;
	height: 32px !important;
}

/* ===== PURRQS MODAL ===== */
.srl-modal-backdrop {
	position: fixed;
	inset: 0;
	background: rgba(15, 23, 42, 0.5);
	backdrop-filter: blur(3px);
	z-index: 1050;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 16px;
}

.srl-modal-container {
	background: #ffffff;
	border-radius: 12px;
	width: 580px;
	max-width: 100%;
	max-height: 90vh;
	display: flex;
	flex-direction: column;
	box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
	border: 1px solid #e2e8f0;
	overflow: hidden;
}

.srl-modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 16px 20px;
	border-bottom: 1px solid #f1f5f9;
}

.srl-modal-title-group {
	display: flex;
	align-items: center;
	gap: 10px;
}

.srl-modal-badge {
	background: #10b981;
	color: #ffffff;
	font-size: 11px;
	font-weight: 700;
	padding: 2px 8px;
	border-radius: 4px;
	letter-spacing: 0.5px;
}

.srl-modal-title {
	margin: 0;
	font-size: 16px;
	font-weight: 600;
	color: #0f172a;
}

.srl-modal-close-btn {
	background: none;
	border: none;
	font-size: 18px;
	color: #64748b;
	cursor: pointer;
	padding: 4px 8px;
	border-radius: 6px;
}

.srl-modal-close-btn:hover {
	background: #f1f5f9;
	color: #0f172a;
}

.srl-modal-body {
	padding: 20px;
	overflow-y: auto;
}

.srl-modal-info-box {
	background: #f8fafc;
	border: 1px solid #e2e8f0;
	border-radius: 8px;
	padding: 12px 14px;
	margin-bottom: 18px;
	display: flex;
	flex-direction: column;
	gap: 6px;
	font-size: 13px;
}

.srl-modal-info-row {
	display: flex;
	justify-content: space-between;
	color: #475569;
}

.srl-modal-info-row strong {
	color: #0f172a;
}

.srl-text-danger {
	color: #ef4444 !important;
}

.srl-modal-section-title {
	font-size: 13px;
	font-weight: 600;
	color: #1e293b;
	margin-bottom: 10px;
	display: flex;
	align-items: center;
	gap: 6px;
}

.srl-section-sub {
	font-size: 11px;
	font-weight: normal;
	color: #64748b;
}

.srl-supplier-list {
	display: flex;
	flex-direction: column;
	gap: 10px;
	margin-bottom: 18px;
}

.srl-supplier-card {
	border: 2px solid #e2e8f0;
	border-radius: 8px;
	padding: 12px 14px;
	cursor: pointer;
	transition: all 0.15s ease;
	background: #ffffff;
}

.srl-supplier-card:hover {
	border-color: #cbd5e1;
	background: #f8fafc;
}

.srl-supplier-card--selected {
	border-color: #10b981 !important;
	background: #f0fdf4 !important;
}

.srl-supplier-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 8px;
}

.srl-supplier-radio-wrap {
	display: flex;
	align-items: center;
	gap: 8px;
}

.srl-supplier-radio-wrap input[type="radio"] {
	accent-color: #10b981;
}

.srl-supplier-name {
	font-weight: 600;
	font-size: 13px;
	color: #0f172a;
}

.srl-supplier-badges {
	display: flex;
	gap: 6px;
}

.srl-badge--default {
	background: #e2e8f0;
	color: #475569;
	font-size: 10px;
	font-weight: 600;
	padding: 2px 6px;
	border-radius: 4px;
}

.srl-badge--savings {
	background: #dcfce7;
	color: #15803d;
	font-size: 10px;
	font-weight: 700;
	padding: 2px 6px;
	border-radius: 4px;
}

.srl-supplier-details {
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: 8px;
	font-size: 11px;
	background: rgba(255, 255, 255, 0.6);
	padding: 8px;
	border-radius: 6px;
}

.srl-supp-col {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.srl-detail-label {
	color: #64748b;
	font-size: 10px;
	text-transform: uppercase;
}

.srl-detail-val {
	font-weight: 600;
	color: #1e293b;
}

.srl-text-primary {
	color: #10b981 !important;
}

.srl-modal-form-group {
	display: flex;
	flex-direction: column;
	gap: 4px;
}

.srl-modal-form-group label {
	font-size: 12px;
	font-weight: 600;
	color: #334155;
}

.srl-modal-footer {
	padding: 14px 20px;
	border-top: 1px solid #f1f5f9;
	background: #f8fafc;
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.srl-modal-summary-text {
	font-size: 13px;
	color: #334155;
}

.srl-modal-summary-text strong {
	color: #0f172a;
}

.srl-modal-actions {
	display: flex;
	gap: 8px;
}

.srl-btn-create-po {
	background: #10b981 !important;
	border-color: #059669 !important;
	color: #ffffff !important;
	font-weight: 600;
}

.srl-btn-create-po:hover {
	background: #059669 !important;
}

/* ===== RESPONSIVE ===== */
@media (max-width: 768px) {
	.srl-filters-row {
		flex-direction: column;
		align-items: stretch;
	}

	.srl-filter-group--item {
		min-width: 100%;
	}

	.srl-summary-cards {
		grid-template-columns: repeat(2, 1fr);
	}

	.srl-item-info-bar {
		flex-direction: column;
		align-items: flex-start;
	}

	.srl-supplier-details {
		grid-template-columns: repeat(2, 1fr);
	}
}
</style>
