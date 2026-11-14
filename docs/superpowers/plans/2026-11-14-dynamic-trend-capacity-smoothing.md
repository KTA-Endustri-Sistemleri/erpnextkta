# Dynamic Trend-Based Capacity Leveling & Smoothing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular, toggleable 3-tier dynamic trend-aware capacity and smoothing engine in KTA MRP that uses historical shipment velocity (`Delivery Note`), finished goods stock accumulation (`Bin`), order volatility ($CV = \sigma / \mu$ via `Sales Order Item` demand series), order cancellation rate ($R_{\text{drop}}$ via `KTA SO Sync Detail`), actual job card unit man-minutes ($t_{\text{man}}$), and Customer Group ceilings (`Customer Group.custom_weekly_capacity`) to solve the 67.3% Work Order delivery delay problem by safely pre-building steady runners into empty preceding weeks while locking erratic items to prevent dead stock.

**Architecture:** Pure, decoupled service architecture under `erpnextkta/kta_mrp/mrp_engine/`. 
- `trends.py`: Pure mathematical functions and batch database aggregators for $V_{\text{actual}}$, $CV$, $R_{\text{drop}}$, $t_{\text{man}}$, $T_{\text{net}}$, $C_{\text{dynamic}}$, and 3-zone leveling classification (Zone A: Runner, Zone B: Medium, Zone C: Erratic/Overstocked).
- `psw.py`: Anti-gasping feasible delivery scheduling for impossible customer due dates ($T_{\text{del}} < T_{\text{prod}} + T_{\text{transit}}$) ensuring Week 1 capacity is shared fairly without displacing regular orders.
- `leveling.py`: 3-zone backward smoothing engine that fully spreads Zone A runner demand, dampens Zone B (max 50%), and locks Zone C ($move\_qty = 0$), strictly preventing load dumping to other items.
- Presentation & Settings: Unified single "Kapasite" and "Doluluk %" columns in `kapasite_planlama_raporu` and `mrp_simulation`, gated behind `KTA MRP Settings.enable_dynamic_trend_smoothing` and runtime report filters for 100% backward compatibility.

**Tech Stack:** Python 3.11+, MariaDB 10.6, Frappe Framework v15, ERPNext v15, Unittest / Frappe Test Runner, HTML/CSS for desk portal docs.

**Spec:** `docs/superpowers/specs/2026-11-14-dynamic-trend-capacity-smoothing-design.md`

## Global Constraints
- Target branch: `main` / production development on `feat/mrp-modular-refactor`.
- Core engine in `erpnextkta/kta_mrp/mrp_engine/` must be 100% pure functions decoupled from presentation/report files (`AGENTS.md` Rule 7).
- No sub-assemblies (flat BOM), Work Order `skip_transfer = 1` (`AGENTS.md` Rule 7).
- Capacity determination follows the 3-Tier Robust Hybrid Model: Micro ($t_{\text{man}} \times \text{Workstation Hours}$), Meso (`Item.custom_weekly_production` sanity-filtered), Macro (`Customer Group.custom_weekly_capacity` ceiling).
- Customer Group ceiling is stored directly on `Customer Group.custom_weekly_capacity` (no unnecessary child DocTypes).
- Two-axis lead time ($T_{\text{prod}}$ vs $T_{\text{transit}}$) must be preserved in feasible schedule projections (`AGENTS.md` Rule 7).
- When `enable_dynamic_trend_smoothing = 0`, existing static leveling math and outputs must remain identical (zero regression).
- Build command: `bench build --app erpnextkta --production` (NEVER `yarn build`, `AGENTS.md` Build Command Rule).
- Documentation under `erpnextkta/www/docs/` must be kept strictly synchronized (`AGENTS.md` Rule 2).
- All commit messages must follow Conventional Commits $\le 72$ chars (`AGENTS.md` Rule 3).

## Review Focus
1. **Empty Weeks in Demand Volatility ($CV$):** If an item is ordered in only 1 of 8 weeks (e.g. 4,000 in W4 and 0 in other weeks), all 8 weeks must be counted in the divisor ($N=8$) so $CV > 1.0$ (erratic/lumpy), rather than filtering out zero weeks which would falsely produce $CV = 0.0$.
2. **No Load Redistribution for Gated Items:** When an erratic item's early pre-build is blocked ($move\_qty = 0$), the unallocated load must NOT be redistributed to other items in the group (which would artificially overstock steady items).
3. **Division by Zero and Sanity Clamping in $C_{\text{dynamic}}$:** If an item has 0 completed job card units or 0 shipments, $t_{\text{man}}$ defaults safely to 0 and falls back to `Item.custom_weekly_production`. If `custom_weekly_production` has an absurd outlier (e.g. 84,000 for a 24k group ceiling), it is clamped to $CG_{P90}$.
4. **Cumulative Smoothing Cap Across Multi-Pass Iterations:** In `leveling.py`, `allowed_move_qty` must act as a cumulative cap across all `ramp_weeks` passes rather than resetting each pass.
5. **Anti-Gasping Feasible Delivery Scheduling:** An overdue order ($PSW < \text{as\_of\_date}$) must enter Week 1 normal demand rather than priority `item_backlog` so it does not displace scheduled regular orders, while its projected feasible delivery date is calculated as $\text{as\_of\_date} + T_{\text{prod}} + T_{\text{transit}}$.

---

### Task 1: Configuration in `KTA MRP Settings`, `Customer Group`, and P90 Seeding Patch

**Files:**
- Modify: `erpnextkta/kta_mrp/custom/customer_group.json`
- Modify: `erpnextkta/kta_mrp/doctype/kta_mrp_settings/kta_mrp_settings.json`
- Modify: `erpnextkta/kta_mrp/mrp_engine/settings.py`
- Create: `erpnextkta/patches/v3_0_3/seed_customer_group_p90_capacities.py`
- Modify: `erpnextkta/patches.txt`
- Modify: `erpnextkta/kta_mrp/mrp_engine/test_settings.py`

**Interfaces:**
- Produces:
  - `Customer Group.custom_weekly_capacity: float`
  - `MrpSettings.enable_dynamic_trend_smoothing: bool = False`
  - `MrpSettings.trend_history_weeks: int = 8`
  - `MrpSettings.cv_high_volatility_threshold: float = 1.0`
  - `MrpSettings.cv_runner_threshold: float = 0.6`
  - `MrpSettings.max_fg_buffer_weeks: float = 2.0`
  - `MrpSettings.order_drop_threshold_pct: float = 25.0`
  - `MrpSettings.enable_dynamic_capacity_calculation: bool = True`

- [ ] **Step 1: Write the failing test for dynamic trend settings and Customer Group capacity**

Add tests to `erpnextkta/kta_mrp/mrp_engine/test_settings.py`:
```python
def test_dynamic_trend_mrp_settings_defaults(self):
    from erpnextkta.kta_mrp.mrp_engine.settings import get_mrp_settings, MrpSettings
    s = MrpSettings()
    self.assertFalse(s.enable_dynamic_trend_smoothing)
    self.assertEqual(s.trend_history_weeks, 8)
    self.assertEqual(s.cv_high_volatility_threshold, 1.0)
    self.assertEqual(s.cv_runner_threshold, 0.6)
    self.assertEqual(s.max_fg_buffer_weeks, 2.0)
    self.assertEqual(s.order_drop_threshold_pct, 25.0)
    self.assertTrue(s.enable_dynamic_capacity_calculation)

    loaded = get_mrp_settings()
    self.assertIsInstance(loaded.enable_dynamic_trend_smoothing, bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_settings`  
Expected: FAIL with `AttributeError: 'MrpSettings' object has no attribute 'enable_dynamic_trend_smoothing'`.

- [ ] **Step 3: Implement settings fields, fixture, and seed patch**

1. In `erpnextkta/kta_mrp/custom/customer_group.json`: Add custom field `custom_weekly_capacity` (Float, Label: "Haftalık Kapasite Tavanı (Adet)", Description: "Bu müşteri grubuna ait ürünler için haftalık maksimum fabrika üretim kapasitesi tavanı (P90)").
2. In `erpnextkta/kta_mrp/doctype/kta_mrp_settings/kta_mrp_settings.json`: Add Section Break `sb_dynamic_trend` with fields `enable_dynamic_trend_smoothing` (Check, default 0), `trend_history_weeks` (Int, default 8), `cv_high_volatility_threshold` (Float, default 1.0), `cv_runner_threshold` (Float, default 0.6), `max_fg_buffer_weeks` (Float, default 2.0), `order_drop_threshold_pct` (Percent, default 25), `enable_dynamic_capacity_calculation` (Check, default 1).
3. In `erpnextkta/kta_mrp/mrp_engine/settings.py`: Add these 7 fields to `MrpSettings` dataclass and map in `get_mrp_settings()` and `resolve_mrp_settings()`.
4. Create patch `erpnextkta/patches/v3_0_3/seed_customer_group_p90_capacities.py`:
   - Seeds `custom_weekly_capacity` on:
     - BOSCH: 92000
     - RATIONAL: 17000
     - Arçelik: 24000
     - TELESET: 21000
     - JK Products / JK: 2000
     - WMF: 4000
5. Register patch in `erpnextkta/patches.txt` and execute migrate on container:
   `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost migrate`

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_settings`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_mrp/custom/customer_group.json erpnextkta/kta_mrp/doctype/kta_mrp_settings/kta_mrp_settings.json erpnextkta/kta_mrp/mrp_engine/settings.py erpnextkta/patches/v3_0_3/seed_customer_group_p90_capacities.py erpnextkta/patches.txt erpnextkta/kta_mrp/mrp_engine/test_settings.py
git commit -m "feat(mrp): add dynamic trend settings and customer group capacity ceiling"
```

---

### Task 2: Pure Calculation Engine & Data Structures in `trends.py`

**Files:**
- Create: `erpnextkta/kta_mrp/mrp_engine/trends.py`
- Create: `erpnextkta/kta_mrp/mrp_engine/test_trends.py`

**Interfaces:**
- Consumes: None (pure functions).
- Produces:
  - `ItemTrendMetrics` (dataclass)
  - `calculate_shipment_velocity(delivery_qtys: list[float], weeks: int = 8) -> float`
  - `calculate_demand_volatility(weekly_demands: list[float], weeks: int = 8) -> float`
  - `calculate_order_drop_rate(total_ordered_qty: float, dropped_qty: float) -> float`
  - `calculate_unit_man_minutes(total_time_mins: float, completed_qty: float) -> float`
  - `calculate_net_workstation_minutes(working_hours_per_day: float, working_days_per_week: int = 6) -> float`
  - `calculate_dynamic_capacity(net_ws_mins: float, active_stations: int, t_man: float, fallback_capacity: float = 0.0, group_p90_ceiling: float = 0.0) -> float`
  - `calculate_available_buffer(actual_stock: float, velocity: float, max_buffer_weeks: float = 2.0) -> float`
  - `determine_leveling_zone(cv: float, order_drop_rate: float, weeks_of_supply: float, cv_runner_threshold: float = 0.6, cv_high_threshold: float = 1.0, max_buffer_weeks: float = 2.0, order_drop_threshold: float = 25.0) -> str`
  - `evaluate_item_trend(...) -> ItemTrendMetrics`

- [ ] **Step 1: Write the failing tests for pure trend and capacity calculations**

Create `erpnextkta/kta_mrp/mrp_engine/test_trends.py`:
```python
import unittest
from erpnextkta.kta_mrp.mrp_engine.trends import (
    calculate_shipment_velocity,
    calculate_demand_volatility,
    calculate_order_drop_rate,
    calculate_unit_man_minutes,
    calculate_net_workstation_minutes,
    calculate_dynamic_capacity,
    calculate_available_buffer,
    determine_leveling_zone,
    evaluate_item_trend,
    ItemTrendMetrics,
)

class TestTrendsPure(unittest.TestCase):
    def test_calculate_demand_volatility_with_empty_weeks(self):
        # 4000 in week 4, 0 in weeks 1, 2, 3, 5, 6, 7, 8 -> N=8
        demands = [0, 0, 0, 4000, 0, 0, 0, 0]
        cv = calculate_demand_volatility(demands, weeks=8)
        self.assertGreater(cv, 2.0)  # Lumpy demand

    def test_calculate_demand_volatility_steady_runner(self):
        demands = [500] * 8
        cv = calculate_demand_volatility(demands, weeks=8)
        self.assertEqual(cv, 0.0)

    def test_calculate_unit_man_minutes_and_dynamic_capacity(self):
        # 1200 man-mins across 600 completed units -> 2.0 min/unit
        t_man = calculate_unit_man_minutes(1200.0, 600.0)
        self.assertEqual(t_man, 2.0)

        # 15 net hours/day * 6 days = 5400 net mins/week
        net_ws_mins = calculate_net_workstation_minutes(15.0, 6)
        self.assertEqual(net_ws_mins, 5400.0)

        # 2 active stations: (5400 * 2) / 2.0 = 5400 units/week
        # Group P90 ceiling is 5000 -> clamped to 5000
        cap = calculate_dynamic_capacity(net_ws_mins, 2, t_man, fallback_capacity=1000, group_p90_ceiling=5000)
        self.assertEqual(cap, 5000.0)

    def test_calculate_dynamic_capacity_fallback_and_outlier_clamp(self):
        # No job card data (t_man = 0) -> fallback to item custom_weekly_production (84000)
        # Clamped by group P90 ceiling (24000)
        cap = calculate_dynamic_capacity(0, 1, 0, fallback_capacity=84000, group_p90_ceiling=24000)
        self.assertEqual(cap, 24000.0)

    def test_determine_leveling_zone(self):
        # Runner: low CV, low drop rate, low stock
        zone_a = determine_leveling_zone(cv=0.2, order_drop_rate=2.0, weeks_of_supply=0.5)
        self.assertEqual(zone_a, "A")

        # Medium volatility
        zone_b = determine_leveling_zone(cv=0.8, order_drop_rate=10.0, weeks_of_supply=1.2)
        self.assertEqual(zone_b, "B")

        # Erratic / Drop risk / Overstock
        zone_c1 = determine_leveling_zone(cv=1.2, order_drop_rate=2.0, weeks_of_supply=0.5)
        self.assertEqual(zone_c1, "C")
        zone_c2 = determine_leveling_zone(cv=0.2, order_drop_rate=30.0, weeks_of_supply=0.5)
        self.assertEqual(zone_c2, "C")
        zone_c3 = determine_leveling_zone(cv=0.2, order_drop_rate=2.0, weeks_of_supply=2.5)
        self.assertEqual(zone_c3, "C")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_trends`  
Expected: FAIL with `ModuleNotFoundError: No module named 'erpnextkta.kta_mrp.mrp_engine.trends'`.

- [ ] **Step 3: Implement pure functions in `erpnextkta/kta_mrp/mrp_engine/trends.py`**

Implement:
- `ItemTrendMetrics` dataclass with fields: `item_code`, `avg_weekly_shipment`, `cv`, `order_drop_rate`, `actual_stock`, `weeks_of_supply`, `available_buffer`, `t_man`, `dynamic_capacity`, `leveling_zone` ("A", "B", "C"), `is_runner`, `is_lumpy`, `is_drop_risk`.
- `calculate_shipment_velocity(delivery_qtys, weeks=8) -> float`: sums deliveries and divides by `max(1, weeks)`.
- `calculate_demand_volatility(weekly_demands, weeks=8) -> float`: pads array with zeros up to `weeks`, computes $\mu = \text{sum} / N$, $\sigma = \sqrt{\sum (x - \mu)^2 / N}$, returns $\sigma / \mu$ if $\mu > 0$ else 0.0.
- `calculate_order_drop_rate(total_ordered_qty, dropped_qty) -> float`: returns `(dropped_qty / total_ordered_qty) * 100` if `total_ordered_qty > 0` else 0.0.
- `calculate_unit_man_minutes(total_time_mins, completed_qty) -> float`: returns `total_time_mins / completed_qty` if `completed_qty > 0` else 0.0.
- `calculate_net_workstation_minutes(working_hours_per_day, working_days_per_week=6) -> float`: returns `working_hours_per_day * 60.0 * working_days_per_week`.
- `calculate_dynamic_capacity(net_ws_mins, active_stations, t_man, fallback_capacity=0.0, group_p90_ceiling=0.0) -> float`: computes capacity, falls back to `fallback_capacity` if `t_man <= 0`, and clamps by `group_p90_ceiling` if $> 0$.
- `calculate_available_buffer(actual_stock, velocity, max_buffer_weeks=2.0) -> float`: returns $\max(0.0, (\text{velocity} \times \text{max\_buffer\_weeks}) - \text{actual\_stock})$.
- `determine_leveling_zone(...) -> str`: returns `"A"`, `"B"`, or `"C"` based on thresholds.
- `evaluate_item_trend(...) -> ItemTrendMetrics`: orchestrates all pure calculations for a single item.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_trends`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_mrp/mrp_engine/trends.py erpnextkta/kta_mrp/mrp_engine/test_trends.py
git commit -m "feat(mrp): implement pure trend, volatility, and dynamic capacity calculations"
```

---

### Task 3: Batch Database Aggregations for Trends (`trends.py`)

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/trends.py`
- Create: `erpnextkta/kta_mrp/mrp_engine/test_trends_db.py`

**Interfaces:**
- Consumes: `tabDelivery Note Item`, `tabDelivery Note`, `tabBin`, `tabSales Order Item`, `tabKTA SO Sync Detail`, `tabJob Card Time Log`, `tabJob Card`, `tabWork Order`, `tabWorkstation Working Hour`, `tabCustomer Group`.
- Produces:
  - `fetch_item_trends(items: list[str], settings=None, as_of_date=None) -> dict[str, ItemTrendMetrics]`

- [ ] **Step 1: Write the failing integration test for `fetch_item_trends`**

Create `erpnextkta/kta_mrp/mrp_engine/test_trends_db.py`:
```python
import unittest
from erpnextkta.kta_mrp.mrp_engine.trends import fetch_item_trends, ItemTrendMetrics

class TestTrendsDatabase(unittest.TestCase):
    def test_fetch_item_trends_returns_graceful_metrics(self):
        # Non-existent or new items should return graceful zero-division safe metrics
        trends = fetch_item_trends(["NON-EXISTENT-ITEM-01", "NON-EXISTENT-ITEM-02"])
        self.assertIn("NON-EXISTENT-ITEM-01", trends)
        m = trends["NON-EXISTENT-ITEM-01"]
        self.assertIsInstance(m, ItemTrendMetrics)
        self.assertEqual(m.avg_weekly_shipment, 0.0)
        self.assertEqual(m.cv, 0.0)
        self.assertEqual(m.actual_stock, 0.0)
        self.assertEqual(m.leveling_zone, "A")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_trends_db`  
Expected: FAIL with `cannot import name 'fetch_item_trends'`.

- [ ] **Step 3: Implement `fetch_item_trends` with optimized bulk SQL queries**

In `erpnextkta/kta_mrp/mrp_engine/trends.py`:
Implement `fetch_item_trends(items: list[str], settings=None, as_of_date=None) -> dict[str, ItemTrendMetrics]`:
1. Parse `settings` (fallback to `get_mrp_settings()`) and `as_of_date` (fallback to `getdate()`).
2. If `items` is empty, return `{}`.
3. Bulk Query 1: `tabDelivery Note Item` joined with `tabDelivery Note` for posting_date between `as_of_date - weeks * 7` and `as_of_date` where `docstatus = 1` and `is_return = 0`.
4. Bulk Query 2: `tabBin` for `actual_qty` where item_code in items.
5. Bulk Query 3: `tabSales Order Item` delivery dates for next 8 weeks grouped by item and week of `delivery_date` where `docstatus = 1` and `delivery_date >= as_of_date`.
6. Bulk Query 4: `tabKTA SO Sync Detail` for `change_type` in `("Miktar Azalışı", "Silinen Satır")` over last `trend_history_weeks`.
7. Bulk Query 5: `tabJob Card Time Log` joined with `tabJob Card` and `tabWork Order` for completed work orders in last 90 days: `SUM(jctl.time_in_mins) / SUM(wo.produced_qty)`.
8. Bulk Query 6: `tabCustomer Group.custom_weekly_capacity` joined via `tabItem.customer` or `tabCustomer.customer_group`.
9. Fallback capacities from `tabItem.custom_weekly_production`.
10. Loop items, call `evaluate_item_trend()`, and return dictionary.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_trends_db`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_mrp/mrp_engine/trends.py erpnextkta/kta_mrp/mrp_engine/test_trends_db.py
git commit -m "feat(mrp): implement bulk database aggregations in fetch_item_trends"
```

---

### Task 4: Anti-Gasping Feasible Delivery in `psw.py`

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/psw.py`
- Modify: `erpnextkta/kta_mrp/mrp_engine/test_psw.py`

**Interfaces:**
- Consumes: `lead_time.py` ($T_{\text{prod}}, T_{\text{transit}}$).
- Produces:
  - `PswRow.is_feasible_delayed: bool`
  - `PswRow.feasible_delivery_date: date`
  - `PswRow.delay_days: int`
  - `PswRow.is_backlog_priority: bool` (False when dynamic trend smoothing is active so it enters regular demand rather than stealing capacity).

- [ ] **Step 1: Write the failing test for anti-gasping feasible PSW**

Add to `erpnextkta/kta_mrp/mrp_engine/test_psw.py`:
```python
def test_impossible_delivery_date_anti_gasping(self):
    from erpnextkta.kta_mrp.mrp_engine.psw import evaluate_production_start_week
    from datetime import date, timedelta
    today = date(2026, 11, 14)
    # Order delivery is in 2 days, but T_prod = 14 days, T_transit = 7 days -> requires 21 days
    impossible_delivery = today + timedelta(days=2)
    
    # When dynamic trend smoothing is active
    row = evaluate_production_start_week(
        delivery_date=impossible_delivery,
        t_prod_days=14,
        t_transit_days=7,
        as_of_date=today,
        dynamic_trend_enabled=True,
    )
    self.assertGreaterEqual(row.psw_date, today)
    self.assertTrue(row.is_feasible_delayed)
    self.assertGreaterEqual(row.delay_days, 19)
    self.assertEqual(row.feasible_delivery_date, today + timedelta(days=21))
    self.assertFalse(row.is_backlog_priority)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_psw`  
Expected: FAIL with `unexpected keyword argument 'dynamic_trend_enabled'`.

- [ ] **Step 3: Implement anti-gasping logic in `psw.py`**

In `psw.py`:
- Update `PswRow` dataclass with fields:
  - `is_feasible_delayed: bool = False`
  - `delay_days: int = 0`
  - `feasible_delivery_date: date = None`
  - `is_backlog_priority: bool = True`
- Add parameter `dynamic_trend_enabled: bool = False` to `calculate_psw` and `evaluate_production_start_week`.
- If `dynamic_trend_enabled` is False: preserve existing behavior (returns ideal PSW, which falls into backlog with `is_backlog_priority = True`).
- If `dynamic_trend_enabled` is True and `ideal_psw < as_of_date`:
  - `psw_date = as_of_date` (starts in current week).
  - `feasible_delivery_date = as_of_date + timedelta(days=t_prod_days + t_transit_days)`.
  - `delay_days = max(0, (feasible_delivery_date - delivery_date).days)`.
  - `is_feasible_delayed = True`.
  - `is_backlog_priority = False` (flags engine to schedule as regular current-week demand).

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_psw`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_mrp/mrp_engine/psw.py erpnextkta/kta_mrp/mrp_engine/test_psw.py
git commit -m "feat(mrp): implement anti-gasping feasible delivery calculations in psw.py"
```

---

### Task 5: 3-Zone Dynamic Backward Smoothing in `leveling.py`

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/leveling.py`
- Create: `erpnextkta/kta_mrp/mrp_engine/test_dynamic_leveling.py`

**Interfaces:**
- Consumes: `ItemTrendMetrics` from `trends.py`.
- Modifies: `backward_rampup_smoothing` signature to accept `dynamic_trend_enabled: bool = False`, `item_trends: dict[str, ItemTrendMetrics] = None`, `item_capacities: dict[str, float] = None`.

- [ ] **Step 1: Write the failing test for dynamic volatility gating and buffer cap**

Create `erpnextkta/kta_mrp/mrp_engine/test_dynamic_leveling.py`:
```python
import unittest
from collections import defaultdict
from erpnextkta.kta_mrp.mrp_engine.leveling import backward_rampup_smoothing
from erpnextkta.kta_mrp.mrp_engine.trends import ItemTrendMetrics

class TestDynamicLeveling(unittest.TestCase):
    def test_backward_smoothing_blocks_zone_c_and_allows_zone_a(self):
        valid_weeks = ["2026-W40", "2026-W41", "2026-W42", "2026-W43"]
        group_capacity = {"KABLO": 1000}
        group_items = {"KABLO": ["ERRATIC-01", "STEADY-02"]}
        
        # In W43: ERRATIC has 800 demand, STEADY has 200 demand (Total load 1000)
        # Previous weeks (W40, W41, W42) are empty (load 0)
        item_plan = {
            "ERRATIC-01": {"2026-W40": 0, "2026-W41": 0, "2026-W42": 0, "2026-W43": 800},
            "STEADY-02": {"2026-W40": 0, "2026-W41": 0, "2026-W42": 0, "2026-W43": 200},
        }
        
        item_trends = {
            "ERRATIC-01": ItemTrendMetrics(
                item_code="ERRATIC-01", avg_weekly_shipment=100, cv=1.8,
                order_drop_rate=30, actual_stock=200, weeks_of_supply=2.0, available_buffer=0,
                t_man=1.0, dynamic_capacity=500, leveling_zone="C",
                is_runner=False, is_lumpy=True, is_drop_risk=True
            ),
            "STEADY-02": ItemTrendMetrics(
                item_code="STEADY-02", avg_weekly_shipment=200, cv=0.1,
                order_drop_rate=0, actual_stock=50, weeks_of_supply=0.25, available_buffer=350,
                t_man=1.0, dynamic_capacity=500, leveling_zone="A",
                is_runner=True, is_lumpy=False, is_drop_risk=False
            ),
        }
        
        backward_rampup_smoothing(
            valid_weeks=valid_weeks,
            group_items=group_items,
            group_capacity=group_capacity,
            item_final_plan=item_plan,
            item_final_kanban_plan=defaultdict(lambda: defaultdict(int)),
            item_final_wo_plan=defaultdict(lambda: defaultdict(int)),
            dynamic_trend_enabled=True,
            item_trends=item_trends,
        )
        
        # ERRATIC-01 is Zone C: MUST NOT be pre-built in earlier weeks (remains 800 in W43)
        self.assertEqual(item_plan["ERRATIC-01"]["2026-W42"], 0)
        self.assertEqual(item_plan["ERRATIC-01"]["2026-W43"], 800)
        # STEADY-02 is Zone A: smoothed backward safely into W42
        self.assertGreater(item_plan["STEADY-02"]["2026-W42"], 0)
        # ERRATIC load must NOT have been dumped into STEADY-02
        self.assertLessEqual(item_plan["STEADY-02"]["2026-W42"], 100)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_dynamic_leveling`  
Expected: FAIL because `backward_rampup_smoothing` does not accept `dynamic_trend_enabled`.

- [ ] **Step 3: Implement 3-zone dynamic smoothing in `leveling.py`**

In `leveling.py`:
- Update `backward_rampup_smoothing(..., dynamic_trend_enabled=False, item_trends=None, item_capacities=None, min_smoothing_qty=10)`:
  - If `dynamic_trend_enabled` is False or `item_trends` is None: run existing static logic untouched (zero regression).
  - If `dynamic_trend_enabled` is True:
    - Maintain `cumulative_moved[item]` across all passes and week pairs.
    - For each item, evaluate its `leveling_zone`:
      - Zone C: `item_cap = 0.0` (Erken üretim kilitli).
      - Zone B: `item_cap = min(rampup_cap * 0.5, item_capacity * 0.5, trend.available_buffer)`.
      - Zone A: `item_cap = min(rampup_cap, item_capacity, trend.available_buffer)`.
    - Remaining item move capability: `rem_cap[item] = max(0.0, item_cap - cumulative_moved[item])`.
    - Only items with `rem_cap[item] > 0` are eligible for backward smoothing.
    - Transferable load is calculated based ONLY on the eligible items' own demand (never redistributing locked Zone C demand).
    - Distribute proportionally among eligible items up to their individual `rem_cap[item]`.
    - Increment `cumulative_moved[item] += share`.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_dynamic_leveling`  
Expected: PASS

- [ ] **Step 5: Run existing leveling test to verify zero regressions**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_leveling`  
Expected: PASS (6/6 tests passing).

- [ ] **Step 6: Commit**

```bash
git add erpnextkta/kta_mrp/mrp_engine/leveling.py erpnextkta/kta_mrp/mrp_engine/test_dynamic_leveling.py
git commit -m "feat(mrp): implement 3-zone dynamic smoothing in leveling.py"
```

---

### Task 6: Orchestration Integration in `service.py`

**Files:**
- Modify: `erpnextkta/kta_mrp/mrp_engine/service.py`
- Modify: `erpnextkta/kta_mrp/mrp_engine/test_service.py`

**Interfaces:**
- Consumes: `trends.py`, `settings.py`, `leveling.py`, `psw.py`.
- Produces: `CapacityPlanResult` containing `item_trends`, trend summary flags, and feasible delayed metadata.

- [ ] **Step 1: Write integration test for CapacityPlanningService with dynamic trends**

Add to `erpnextkta/kta_mrp/mrp_engine/test_service.py`:
```python
def test_capacity_planning_service_with_dynamic_trend_toggle(self):
    from erpnextkta.kta_mrp.mrp_engine.service import CapacityPlanningService
    service = CapacityPlanningService(dynamic_trend_enabled=True)
    result = service.run()
    self.assertTrue(result.dynamic_trend_enabled)
    self.assertIsNotNone(result.item_trends)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_service`  
Expected: FAIL with attribute error or parameter error.

- [ ] **Step 3: Integrate trends into `CapacityPlanningService`**

In `service.py`:
- In `CapacityPlanningService.__init__`: accept optional `dynamic_trend_enabled: bool = None`. If None, read from `get_mrp_settings().enable_dynamic_trend_smoothing`.
- If active, call `fetch_item_trends(group_items, settings=self.settings, as_of_date=self.as_of_date)`.
- Pass dynamic capacities and `item_trends` into `backward_rampup_smoothing`.
- Pass `dynamic_trend_enabled` to `evaluate_production_start_week`.
- Store `item_trends` and `dynamic_trend_enabled` in `CapacityPlanResult`.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_service`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add erpnextkta/kta_mrp/mrp_engine/service.py erpnextkta/kta_mrp/mrp_engine/test_service.py
git commit -m "feat(mrp): orchestrate dynamic trend smoothing in CapacityPlanningService"
```

---

### Task 7: Presentation Layer in Capacity Report & Simulation UI

**Files:**
- Modify: `erpnextkta/kta_mrp/report/kapasite_planlama_raporu/kapasite_planlama_raporu.js`
- Modify: `erpnextkta/kta_mrp/report/kapasite_planlama_raporu/kapasite_planlama_raporu.py`
- Modify: `erpnextkta/kta_mrp/page/mrp_simulation/mrp_simulation.js`
- Modify: `erpnextkta/kta_mrp/page/mrp_simulation/mrp_simulation.py`

**Interfaces:**
- Filter: `"dynamic_trend_smoothing"` (Check, default 0) in report and simulation page.
- Columns: Single unified "Kapasite" and "Doluluk %" columns (no messy multi-column sprawl).
- Warning Badges:
  - Zone C: Violet badge (`#8b5cf6`, `fa-bolt`, "Yüksek Oynaklık / Erken Üretim Kilitli")
  - Overstock Brake: Cyan badge (`#06b6d4`, `fa-shield`, "Ambar Kapsama Freni")
  - Feasible Delay: Amber/Red badge (`#ef4444`, `fa-calendar-times-o`, "Yetişmez: +X gün")

- [ ] **Step 1: Add dynamic trend filter and badge handlers in report and simulation**

In `kapasite_planlama_raporu.js` and `mrp_simulation.js`:
Add filter:
```javascript
{
    fieldname: "dynamic_trend_smoothing",
    label: __("Dinamik Trend Dengeleme (CV & Ambar Freni)"),
    fieldtype: "Check",
    default: 0
}
```
In python reporting files: Pass `dynamic_trend_smoothing` filter into `CapacityPlanningService` and format the badges on item code cells and matrix cells.

- [ ] **Step 2: Run production frontend build command**

Run: `docker exec -u frappe erpnext-dev-frappe-1 bench build --app erpnextkta --production`  
Expected: Exit code 0.

- [ ] **Step 3: Commit**

```bash
git add erpnextkta/kta_mrp/report/kapasite_planlama_raporu/ erpnextkta/kta_mrp/page/mrp_simulation/
git commit -m "feat(ui): add dynamic trend filter and warning badges to capacity report and simulation"
```

---

### Task 8: Web Portal Documentation Sync (`erpnextkta/www/docs/`)

**Files:**
- Modify: `erpnextkta/www/docs/mrp-overview.html`
- Modify: `erpnextkta/www/docs/mrp-simulation.html`
- Modify: `erpnextkta/www/docs/production-start-week.html`

- [ ] **Step 1: Update documentation pages with Dynamic Trend Leveling rules**

Add clear documentation sections with clean HTML tags (no raw LaTeX):
- Document the 3-Tier Robust Hybrid Capacity calculation (Micro, Meso, Macro).
- Document the 3-Zone Dynamic Leveling logic (Zone A full smoothing, Zone B dampened max 50%, Zone C locked).
- Document the Anti-Gasping Feasible Delivery rule for impossible customer dates.
- Document the 3 status warning badges.

- [ ] **Step 2: Verify portal cache clearing**

Run:
```bash
docker exec -u frappe erpnext-dev-frappe-1 bench build --app erpnextkta --production
docker exec -u frappe erpnext-dev-frappe-1 bench clear-cache
docker exec -u frappe erpnext-dev-frappe-1 bench clear-website-cache
```

- [ ] **Step 3: Commit**

```bash
git add erpnextkta/www/docs/
git commit -m "docs(mrp): document dynamic trend leveling and anti-gasping rules in desk portal"
```

---

### Task 9: Full Test Suite Verification

**Files:**
- Verify all unit and integration test suites: `test_settings`, `test_trends`, `test_trends_db`, `test_psw`, `test_dynamic_leveling`, `test_leveling`, `test_service`.

- [ ] **Step 1: Run complete MRP engine test suite in Docker container**

Run:
```bash
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_settings
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_trends
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_trends_db
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_psw
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_dynamic_leveling
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_leveling
docker exec -u frappe erpnext-dev-frappe-1 bench --site development.localhost run-tests --module erpnextkta.kta_mrp.mrp_engine.test_service
```
Expected: 100% PASS with 0 failures or errors.

- [ ] **Step 2: Commit plan completion**

```bash
git commit --allow-empty -m "chore(mrp): verify all dynamic trend tests and finalize feature implementation"
```
