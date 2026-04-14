# ARC
Solutions for ARC-AGI https://arcprize.org/

NEURO-SYMBOLIC ARC SOLVER
Architecture & Design Document
==============================

## 1. SYSTEM OVERVIEW

The Neuro-Symbolic ARC Solver is a production-ready Python system designed to tackle
the ARC-AGI (Abstract Reasoning Challenge) through a structured reasoning loop:

    INPUT TASK
        ↓
    [PERCEIVE] - Analyze grids, identify patterns
        ↓
    [HYPOTHESIZE] - Generate transformation rules
        ↓
    [CODE] - Write Python function
        ↓
    [VERIFY] - Test on training examples
        ├─ SUCCESS → [SOLVE] Apply to test input
        └─ FAILURE → [REFINE] & retry (max 5 times)
        ↓
    OUTPUT SOLUTION

## Current Analysis Deliverables

- `FINDINGS.md` summarizes the current ARC split and baseline conclusions.
- `docs/index.html` is the lightweight dashboard intended for GitHub Pages.
- The dashboard focuses on taxonomy splits, baseline families, and the main conclusion that hard object/compositional categories remain the weak region.
