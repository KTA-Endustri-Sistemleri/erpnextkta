# KTA MRP Engine and RPO Report Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve work order carry-over loss in capacity leveling, prevent duplicate raw material requirements in mono BOM setups, enable multi-supplier individual lead-time shifting and past-due order clamping in the Recommended Purchase Orders (RPO) report, and integrate zero-impact safety stock and hybrid supplier nationality checks into the MRP engine.

**Architecture:** Pure algorithmic fixes in `leveling.py` and `netting.py` followed by data-flow integration in `service.py`/`supply.py` and presentation expansion in `recommended_purchase_orders.py`. Preserves the mono-BOM and `skip_transfer = 1` operational baseline while ensuring mathematical integrity across capacity leveling and inventory netting.

**Tech Stack:** Python 3.12, Frappe Framework v15, MariaDB, ERPNext Manufacturing/Stock modules.

**Spec:** [docs/superpowers/specs/2026-11-13-mrp-engine-corrections-design.md](file:///home/frappe/frappe-bench/apps/erpnextkta/docs/superpowers/specs/2026-11-13-mrp-engine-corrections-design.md)

## Global Constraints
- Target branch is `feat/mrp-modular-refactor` (merging to `main`).
- Never run `yarn build` directly; use `bench build --app erpnextkta --production` if frontend builds are needed.
- All commit messages must strictly follow Conventional Commits (`fix(mrp): ...`, `feat(mrp): ...`, `test(mrp): ...`).
- All tests must pass via `bench --site old.kta-endustri.com.tr run-tests --module <module_name>`.
- Default behavior for `safety_stock` must remain `0` (zero impact on existing items without configured safety stock).

## Review Focus
- **Input / Condition 1:** Work Order backlog exceeds group capacity in week 1 (`remaining_cap <= 0`). Expected: All current week work orders are carried over to subsequent weeks without dropping any quantity.
- **Input / Condition 2:** Multi-sourcing item has net shortage smaller than sum of supplier MOQs. Expected: Order is consolidated to the primary/highest quota supplier instead of generating bloated orders across all suppliers.
- **Input / Condition 3:** Recommended PO has a lead time that exceeds the time between today and the need week. Expected: Order week clamps to the current planning week with an urgent indicator, never opening past-due week columns.
- **Input / Condition 4:** Supplier country in ERPNext was left as 'Turkey' by mistake, but `supplier_group` is 'YD-Hammadde'. Expected: `is_foreign_supplier()` classifies it as foreign/import.
- **Input / Condition 5:** Item has `safety_stock` in ERPNext Purchasing tab. Expected: Netting formula triggers shortage when available stock drops below safety stock, rather than when it drops below zero.

---

### Task 1: Fix Work Order Carry-Over in Leveling (`leveling.py` & `test_leveling.py`)

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/leveling.py:120-135`
- Test: `erpnextkta/kta_mrp/mrp_engine/test_leveling.py`

**Interfaces:**
- Consumes: `item_week_wo`, `item_carry_over_wo`
- Produces: Complete `item_final_wo_plan` preserved across capacity-saturated weeks.

- [ ] **Step 1: Write the failing test in `test_leveling.py`**

Add `test_forward_scheduling_preserves_wo_carry_over_when_capacity_full` to [test_leveling.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/test_leveling.py):
```python
def test_forward_scheduling_preserves_wo_carry_over_when_capacity_full(self):
    """Test that when remaining_cap <= 0 in a week, item_week_wo is carried over rather than lost."""
    valid_weeks = ["2026_w46", "2026_w47"]
    group_items = {"GRP": ["ITEM1"]}
    group_capacity = {"GRP": 1000}
    # Backlog consumes all 1000 capacity in week 46
    item_backlog = {"ITEM1": 1000}
    item_backlog_wo = {"ITEM1": 1000}
    # Week 46 has an additional new WO of 500 units
    item_week_demand = {"ITEM1": {"2026_w46": 500, "2026_w47": 0}}
    item_week_wo = {"ITEM1": {"2026_w46": 500, "2026_w47": 0}}

    plan, kanban, wo_plan = forward_scheduling(
        valid_weeks=valid_weeks,
        group_items=group_items,
        group_capacity=group_capacity,
        item_backlog=item_backlog,
        item_week_demand=item_week_demand,
        item_backlog_wo=item_backlog_wo,
        item_week_wo=item_week_wo,
        leveling_enabled=True,
    )

    # In week 46, backlog WO (1000) is produced
    self.assertEqual(wo_plan["ITEM1"]["2026_w46"], 1000)
    # In week 47, the 500 unit WO that couldn't fit in week 46 must carry over and be produced
    self.assertEqual(wo_plan["ITEM1"]["2026_w47"], 500)
    # Total WO plan across all weeks must equal 1500, with 0 lost
    self.assertEqual(sum(wo_plan["ITEM1"].values()), 1500)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.mrp_engine.test_leveling`  
Expected: FAIL with `AssertionError: 0 != 500` or `1000 != 1500`.

- [ ] **Step 3: Implement the fix in `leveling.py`**

In [leveling.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/leveling.py#L127-L131), in the `else` block of current demand distribution inside `forward_scheduling`, add the missing carry over for work orders:
```python
					else:
						for i in items_in_group:
							item_carry_over[i] += item_week_demand[i].get(week, 0)
							item_carry_over_kanban[i] += item_week_kanban[i].get(week, 0)
							item_carry_over_wo[i] += item_week_wo[i].get(week, 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.mrp_engine.test_leveling`  
Expected: PASS with all tests passing.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_mrp/mrp_engine/leveling.py erpnextkta/kta_mrp/mrp_engine/test_leveling.py
git commit -m "fix(mrp): preserve work order carry over when weekly capacity is saturated"
```

---

### Task 2: Safety Stock Support & MOQ Consolidation in Netting (`netting.py` & `test_netting.py`)

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/netting.py`
- Test: `erpnextkta/kta_mrp/mrp_engine/test_netting.py`

**Interfaces:**
- Consumes: `safety_stock: float = 0`, `suppliers: list`
- Produces: `NettingResult` with safety stock enforcement and consolidated MOQ for small shortages.

- [ ] **Step 1: Write failing tests in `test_netting.py`**

Add tests to [test_netting.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/test_netting.py):
```python
def test_net_material_respects_safety_stock(self):
    """When safety stock is set, shortage triggers before free stock reaches zero."""
    weeks = ["2026_w46", "2026_w47"]
    gross = {"2026_w46": 50, "2026_w47": 50}
    # Free stock is 80, safety stock is 40. Demand in w46 is 50 -> remaining 30 < 40 safety stock!
    res = net_material(weeks, gross, free_stock=80, safety_stock=40, pack=1)
    # In w46, shortage must be (50 + 40) - 80 = 10
    self.assertEqual(res.net["2026_w46"], 10)
    self.assertEqual(res.planned_orders["2026_w46"], 10)

def test_quota_small_shortage_consolidates_to_primary_supplier(self):
    """When net shortage < sum of MOQs, consolidate to primary supplier to prevent bullwhip over-ordering."""
    weeks = ["2026_w46"]
    gross = {"2026_w46": 100}
    suppliers = [
        {"supplier": "SupA", "quota_share": 60, "moq": 500, "pack": 100},
        {"supplier": "SupB", "quota_share": 40, "moq": 500, "pack": 100},
    ]
    res = net_material(
        weeks,
        gross,
        free_stock=0,
        sourcing_strategy="Kotalı Dağılım (% Paylaşım)",
        suppliers=suppliers,
    )
    # Instead of ordering 500 from SupA AND 500 from SupB (1000 total), order 500 from primary SupA
    self.assertEqual(res.planned_orders["2026_w46"], 500)
    self.assertEqual(res.planned_orders_by_supplier["SupA"]["2026_w46"], 500)
    self.assertEqual(res.planned_orders_by_supplier.get("SupB", {}).get("2026_w46", 0), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.mrp_engine.test_netting`  
Expected: FAIL with `unexpected keyword argument 'safety_stock'` or `AssertionError: 1000 != 500`.

- [ ] **Step 3: Implement safety stock and MOQ guard in `netting.py`**

In [netting.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/netting.py):
1. Update `net_material` signature to accept `safety_stock=0`:
```python
def net_material(
	weeks,
	gross,
	free_stock=0,
	receipts=None,
	moq=0,
	pack=1,
	safety_stock=0,
	sourcing_strategy="Varsayılan Tedarikçi (%100)",
	suppliers=None,
):
```
2. Pass `safety_stock` into `_net_week`.
3. In `_net_week`, update shortage calculation:
```python
	available = balance + receipt
	shortage = max(0.0, demand + flt(safety_stock) - available)
```
4. In `_net_week`, update kotalı dağıtım to guard against MOQ explosion when `shortage < total_moq`:
```python
	if len(suppliers) > 1 and sourcing_strategy == "Kotalı Dağılım (% Paylaşım)":
		total_moq_sum = sum(flt(s.get("moq") or 0) for s in suppliers)
		if total_moq_sum > 0 and shortage < total_moq_sum:
			# Small requirement: Consolidate to highest quota supplier
			best_s = max(suppliers, key=lambda s: (flt(s.get("quota_share") or 0), s.get("idx", 0)))
			sup_name = best_s.get("supplier")
			order = lot_size(shortage, moq=best_s.get("moq", 0), pack=best_s.get("pack", 1))
			if sup_name not in result.planned_orders_by_supplier:
				result.planned_orders_by_supplier[sup_name] = {}
			result.planned_orders_by_supplier[sup_name][week] = order
		else:
			for s in suppliers:
				sup_name = s.get("supplier")
				quota = flt(s.get("quota_share") or 0) / 100.0
				s_shortage = shortage * quota
				s_order = lot_size(s_shortage, moq=s.get("moq", 0), pack=s.get("pack", 1))
				if sup_name not in result.planned_orders_by_supplier:
					result.planned_orders_by_supplier[sup_name] = {}
				result.planned_orders_by_supplier[sup_name][week] = s_order
				order += s_order
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.mrp_engine.test_netting`  
Expected: PASS with all tests passing.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_mrp/mrp_engine/netting.py erpnextkta/kta_mrp/mrp_engine/test_netting.py
git commit -m "feat(mrp): support safety stock and consolidate multi-sourcing moq on small shortages"
```

---

### Task 3: Service & Supply Safety Stock Extraction and Hybrid Supplier Check (`service.py`, `supply.py`)

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/supply.py`, `erpnextkta/kta_mrp/mrp_engine/service.py`
- Test: `erpnextkta/kta_mrp/mrp_engine/test_supply.py`, `erpnextkta/kta_mrp/mrp_engine/test_service.py`

**Interfaces:**
- Consumes: `Item.safety_stock`, `Supplier.country`, `Supplier.supplier_group`
- Produces: `is_foreign_supplier()` helper function and `material.safety_stock` passed to netting.

- [ ] **Step 1: Write failing tests in `test_supply.py`**

Add unit tests to [test_supply.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/test_supply.py):
```python
def test_is_foreign_supplier_hybrid_rule(self):
    """Foreign supplier check respects both country != Turkey and supplier_group == 'YD-Hammadde'."""
    from erpnextkta.kta_mrp.mrp_engine.supply import is_foreign_supplier
    # Foreign country
    self.assertTrue(is_foreign_supplier(frappe._dict(country="Germany", supplier_group="YD-Hammadde")))
    # Country left as Turkey by mistake but group is YD-Hammadde
    self.assertTrue(is_foreign_supplier(frappe._dict(country="Turkey", supplier_group="YD-Hammadde")))
    # Domestic supplier
    self.assertFalse(is_foreign_supplier(frappe._dict(country="Turkey", supplier_group="Yİ-Hammadde")))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.mrp_engine.test_supply`  
Expected: FAIL with `cannot import name 'is_foreign_supplier'`.

- [ ] **Step 3: Implement `is_foreign_supplier` and `safety_stock` extraction**

1. In [supply.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/supply.py):
```python
def is_foreign_supplier(supplier_info, company_country="Turkey"):
	"""Tedarikçinin yurt dışı / ithalat statüsünde olup olmadığını belirler."""
	if not supplier_info:
		return False
	country = supplier_info.get("country")
	group = supplier_info.get("supplier_group")
	if group == "YD-Hammadde":
		return True
	if country and country != company_country:
		return True
	return False
```
2. In [service.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/mrp_engine/service.py):
   * Add `safety_stock: float = 0` to `MaterialRequirement` dataclass.
   * In `load_supply_context`, query `safety_stock` in `item_meta`:
     `item_meta=get_item_meta(item_codes, ["item_name", "stock_uom", "safety_stock"])`
   * In `build_material`, read `safety_stock = flt(item_meta.get("safety_stock") or 0)` and pass `safety_stock=safety_stock` into `net_material()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.mrp_engine.test_supply`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_mrp/mrp_engine/supply.py erpnextkta/kta_mrp/mrp_engine/service.py erpnextkta/kta_mrp/mrp_engine/test_supply.py
git commit -m "feat(mrp): integrate item safety stock and hybrid supplier foreign check"
```

---

### Task 4: RPO Multi-Supplier Expansion and Past-Due Clamping (`recommended_purchase_orders.py`)

**Files:**
- Modify: `erpnextkta/kta_mrp/report/recommended_purchase_orders/recommended_purchase_orders.py`
- Test: `erpnextkta/kta_mrp/report/recommended_purchase_orders/test_recommended_purchase_orders.py`

**Interfaces:**
- Consumes: `material.planned_orders_by_supplier`, `material.suppliers_quota`, `lead_time_days`
- Produces: Expanded rows per supplier with individual lead times and clamping to current week.

- [ ] **Step 1: Write failing test in `test_recommended_purchase_orders.py`**

Add unit test to [test_recommended_purchase_orders.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/report/recommended_purchase_orders/test_recommended_purchase_orders.py):
```python
def test_rpo_expands_multi_supplier_and_clamps_past_due(self):
    """RPO generates separate rows for split suppliers with individual lead times and clamps past weeks."""
    from erpnextkta.kta_mrp.report.recommended_purchase_orders.recommended_purchase_orders import build_order_rows
    # Construct mock material with 2 suppliers and a long lead time in one
    # Verify separate rows are produced and orders falling before first_week clamp to first_week with is_past_due=True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.report.recommended_purchase_orders.test_recommended_purchase_orders`  
Expected: FAIL.

- [ ] **Step 3: Implement multi-supplier expansion and past-due clamping**

In [recommended_purchase_orders.py](file:///home/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_mrp/report/recommended_purchase_orders/recommended_purchase_orders.py):
1. Update `shift_by_lead_time` to accept specific supplier orders and `lead_time_days`.
2. When shifting, if `order_date < week_start(first_valid_week)`:
   * Target week is set to `first_valid_week`.
   * Flag `is_past_due = 1` is recorded on row.
3. In `execute()`, iterate over materials:
   * If `material.planned_orders_by_supplier` has multiple suppliers, produce a row for each supplier with that supplier's `moq`, `pack`, `lead_time_days`, and shifted weeks.
   * If single supplier, maintain single row.
4. Add column `is_past_due` or indicator in row rendering.

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.report.recommended_purchase_orders.test_recommended_purchase_orders`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_mrp/report/recommended_purchase_orders/recommended_purchase_orders.py erpnextkta/kta_mrp/report/recommended_purchase_orders/test_recommended_purchase_orders.py
git commit -m "feat(mrp): expand multi-supplier rows and clamp past due orders in rpo report"
```

---

### Task 5: End-to-End Live Integration Verification (`8750301805`) & Documentation

**Files:**
- Create/Execute: `scratch/verify_live_mrp.py`
- Modify: `docs/material_requirement.md`, `docs/recommended_purchase_orders.md`

- [ ] **Step 1: Execute end-to-end live verification script on `8750301805`**

Run verification script across the full pipeline (`get_material_requirements`):
- Verify that `MFG-WO-2026-05215` (3,280 pending) and `MFG-WO-2026-05434` (5,000 pending) both deduct properly from demand.
- Confirm that total WO deducted equals 8,280 and driving quantity is 18,120 (0 lost WO).
- Confirm that 55 raw materials in `BOM-8750301805-005` have 0 duplicate requirements generated.

- [ ] **Step 2: Update documentation markdown files**

Update [material_requirement.md](file:///home/frappe/frappe-bench/apps/erpnextkta/docs/material_requirement.md) and [recommended_purchase_orders.md](file:///home/frappe/frappe-bench/apps/erpnextkta/docs/recommended_purchase_orders.md) with:
- Explanation of the work order carry-over mechanism in mono BOM setups.
- Multi-supplier row breakdown in Recommended Purchase Orders.
- Safety stock configuration via Item Purchasing tab.
- Hybrid foreign supplier detection logic.

- [ ] **Step 3: Run full automated test suite**

Run:
```bash
bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.mrp_engine.test_leveling
bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.mrp_engine.test_netting
bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.mrp_engine.test_supply
bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.report.material_requirement.test_material_requirement
bench --site old.kta-endustri.com.tr run-tests --module erpnextkta.kta_mrp.report.recommended_purchase_orders.test_recommended_purchase_orders
```
Expected: All tests pass (0 failures, 0 errors).

- [ ] **Step 4: Commit documentation and plan updates**

```bash
git add docs/ docs/superpowers/
git commit -m "docs(mrp): document carry-over fix, multi-sourcing rpo and safety stock"
```
