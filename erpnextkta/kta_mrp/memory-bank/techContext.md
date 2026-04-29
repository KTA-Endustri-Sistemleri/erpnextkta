# Technical Context: KTA MRP

## Technologies
- **Core**: Frappe Framework (Python 3.x, MariaDB).
- **Frontend**: Vanilla JS (Frappe Script Reports).
- **Libraries**: `math` (for rounding), `collections.defaultdict` (for data structures).

## Development Setup
- Custom App: `kta_mrp`.
- Main Report Files:
    - `capacity_planning_report.py/js`
    - `work_order_planning.py/js`
    - `material_requirement.py/js`
    - `report_utils.py` (Common utilities and filters).

## Technical Constraints
- **Weekly Resolution**: All planning is done in ISO weeks (YYYY-Www).
- **"ÜRÜN" Filter**: Only items with `custom_ara_malzeme_grubu == "ÜRÜN"` are considered in the primary production plan.
- **Performance**: Material Requirement triggers a full capacity recalculation, so filters should be used to limit date ranges.

## Dependencies
- Relies on `ProductionStartWeekReport` for initial demand data.
- Relies on `Item Group` custom fields for capacity definitions.
- Relies on `Item Supplier` child table for MOQ definitions.
