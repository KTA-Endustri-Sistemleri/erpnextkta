# Active Context: KTA MRP Optimization

## Current Work Focus
Refining the end-to-end planning chain from capacity to material requirements.

## Recent Changes
- **Hybrid Balancing**: Implemented FIFO + Criticality logic in Capacity Planning.
- **Linear Ramp-up**: Added a backward smoothing pass to create a 3-week linear growth curve for spikes.
- **MOQ Integration**: Updated Material Requirement to fetch `custom_moq` from the default supplier and round up net needs accordingly.
- **Modular Filters**: Added `dengeleme_yapilsin`, `ramp_up_aktif`, and `ramp_up_weeks` filters across all related reports.
- **Bug Fix**: Resolved unpacking error in Material Requirement when calling the updated Capacity Planning report.

## Next Steps
- **Validation**: Monitor the "Order Surplus" (Stock overflow) created by MOQ rounding over multiple weeks.
- **UI Enhancement**: Consider adding a "Setup Time" penalty if we switch between too many items in a single week.
- **Optimization**: Profile the Material Requirement report for very large item sets.

## Active Decisions
- **Ramp-up Target**: Set to 3 weeks by default as the optimal balance for KTA factory operations.
- **Unfulfilled Demand**: Always carried forward to ensure zero data loss in the planning chain.
