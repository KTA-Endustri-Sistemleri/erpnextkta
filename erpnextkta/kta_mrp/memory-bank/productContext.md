# Product Context: KTA MRP System

## Why this project exists?
The standard ERPNext planning tools often treat items independently, leading to "artificial capacity duplication" (where two items in the same group both think they have full capacity). Additionally, demand spikes often lead to unachievable production plans (10,000 units in Week 1, 0 in Week 2).

## Problems Solved
- **Unrealistic Plans**: Prevents "spike" weeks by spreading load backward (Ramp-up) and forward (Carry-over).
- **Group Bottlenecks**: Items sharing the same machine/line are now capped by a shared group capacity.
- **Backlog Management**: Ensures oldest orders are produced first without burying new ones.
- **Purchasing Stress**: Material requirements are now smoothed, preventing sudden "need everything tomorrow" crises.

## How it works
The system follows a 3-layer chain:
1.  **Capacity Planning**: The "Brain". Calculates the optimal weekly production per item.
2.  **Work Order Planning**: The "Action". Compares the plan with existing Work Orders and suggests new ones.
3.  **Material Requirement**: The "Supply". Explodes BOMs based on the plan and calculates net needs considering Stock, POs, and MOQ.

## User Experience Goals
- **Clarity**: Visual cues (cell colors) for capacity utilization.
- **Control**: Modular toggles for Balancing and Ramp-up.
- **Reliability**: A plan that a production manager can actually sign off on and a purchasing agent can execute.
