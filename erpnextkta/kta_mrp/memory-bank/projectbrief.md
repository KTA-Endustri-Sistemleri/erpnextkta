# Project Brief: KTA MRP & Capacity Planning Optimization

## Core Requirements
Modernize the ERPNext KTA capacity planning workflow to move beyond independent product capacity calculations to a shared, group-based model with intelligent load leveling.

## Goals
1.  **Shared Capacity**: Implement a model where items in the same group share a common weekly production limit.
2.  **Intelligent Balancing**: Use a hybrid FIFO (Backlog first) and Criticality-based (Proportional) distribution strategy.
3.  **Production Smoothing (Heijunka)**: Eliminate sudden spikes in production through a linear ramp-up algorithm.
4.  **Operational Accuracy**: Ensure that work order suggestions and material requirements are synchronized with the balanced production plan.
5.  **Logistics Optimization**: Implement MOQ (Minimum Order Quantity) and packaging size rounding for raw materials.
