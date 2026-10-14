# Agentic Memory for CyVerACT

**Diploma thesis by Olga Giannouchou**  
School of Electrical and Computer Engineering, National Technical University of Athens (NTUA), 2026.

**Thesis:** *Διαχείριση μνήμης σε συνομιλιακούς AI πράκτορες για την υποστήριξη ερωτημάτων πάνω σε γράφους γνώσης.*

This project extends the original **CyVerACT** Text-to-Cypher workflow with memory mechanisms for reusing previous solutions and validation errors. It combines **Generator Helper**, **short-term History**, **Trajectory Retrieval**, and predefined **FixRules** with CyVerACT's validation and correction loop.

The implementation and thesis experiments are in [`CyVerACT/extended_workflow/`](CyVerACT/extended_workflow/).

## Getting started

Python **3.11**, Neo4j, and an OpenRouter API key are required for the current notebook setup. The main entry points are:

- [`run_reproducible_workflow.ipynb`](CyVerACT/extended_workflow/run_reproducible_workflow.ipynb) — single queries, custom Excel datasets, and Movies/MultiDB experiments; supports runtime memory configurations.
- [`get_main_workflow_results.ipynb`](CyVerACT/extended_workflow/get_main_workflow_results.ipynb) — the established Movies and MultiDB experiment runner.

Setup, execution steps, dataset formats, memory architecture, experimental configurations, results, and reproducibility notes are documented in the **[project Wiki](../../wiki)**.

## Attribution

This thesis extension was developed by **Olga Giannouchou** and builds on the original **CyVerACT** research workflow. Original framework code, benchmark material, and contributor information are retained in [`CyVerACT/README.md`](CyVerACT/README.md). The original repository identifies the [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license; see the repository's license file for terms.