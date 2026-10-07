# Agentic Memory for CyVerACT

This repository contains the original **CyVerACT** Text-to-Cypher workflow together with a memory-enhanced extension developed for the NTUA/ECE diploma thesis:

> **«Διαχείριση μνήμης σε συνομιλιακούς AI πράκτορες για την υποστήριξη ερωτημάτων πάνω σε γράφους γνώσης.»**

The thesis extension investigates whether a Text-to-Cypher agent can reuse experience from previous executions by storing and retrieving successful solutions, failed Cypher attempts, validation errors, and correction trajectories in a dedicated Neo4j memory graph.

The main thesis implementation is located under:

```text
CyVerACT/extended_workflow/
```

The rest of the repository also preserves the original CyVerACT code and earlier exploratory/testing material.

---

## Overview

The extended workflow preserves the original CyVerACT validation-and-correction loop and adds three memory mechanisms:

- **Generator Helper** — retrieves a semantically similar previously resolved question and successful Cypher query before initial generation.
- **History** — provides the Cypher Corrector with failed attempts from the current execution.
- **Trajectory Retrieval** — retrieves related historical failures and successful correction trajectories from long-term memory.

The workflow follows:

```text
Schema Filtering
    ↓
Cypher Generator
    ↓
CyVer Evaluator
    ├── valid → Cypher Executor → Output
    └── errors → Cypher Corrector → CyVer Evaluator
                         ↓
              Full-schema fallback
              after filtered-schema limit
```

The experiments use:

- 5 correction attempts with the filtered schema;
- up to 10 total attempts after full-schema fallback;
- LangGraph `recursion_limit = 50`.

The evaluator combines CyVer syntax, schema, and property validators.

![Extended CyVerACT workflow](CyVerACT/extended_workflow/Images/extended_graph.png)

---

## Memory architecture

Long-term memory is stored in a Neo4j graph that is logically separate from the target knowledge graph.

```text
(Question)-[:RESOLVED_WITH]->(Answer)
    |
    +--[:HAS_ATTEMPT]->(Attempt)
                           |
                           +--[:CAUSED_ERROR]->(CypherError)
                                                    |
                                                    +--[:HAS_ERROR_TYPE]->(ErrorType)
                                                                               |
                                                                               +--[:FIXED_WITH]->(FixRule)
```

Main node types:

| Node | Purpose |
|---|---|
| `Question` | Natural-language question and optional embedding |
| `Attempt` | Generated/corrected Cypher attempt |
| `CypherError` | Validation/database error plus retrieval embeddings |
| `ErrorType` | Canonical CyVer error/warning type |
| `FixRule` | Predefined correction guidance |
| `Answer` | Successfully executed validator-clean Cypher |

The implementation uses `sentence-transformers/all-MiniLM-L6-v2` embeddings with 384 dimensions and cosine similarity.

| Representation | Neo4j vector index | Use |
|---|---|---|
| `Question.embedding` | `question_embeddings` | Similar successful-question retrieval |
| `CypherError.error_embedding` | `error_vector_embeddings` | Candidate retrieval by error similarity |
| `CypherError.trajectory_embedding` | `trajectory_vector_embeddings` | Stored trajectory representation |

Generator Helper uses a question-similarity threshold of **0.93**.

Trajectory retrieval first obtains candidates from the error vector index and then combines error similarity with direct trajectory cosine similarity:

```text
score = 0.7 × error_similarity + 0.3 × trajectory_similarity
```

Candidates are retained when the combined score is at least **0.80**.

---

## Experimental configurations

Seven configurations are evaluated:

| Configuration | History | Trajectory Retrieval | Generator Helper |
|---|:---:|:---:|:---:|
| Baseline | — | — | — |
| History Only | ✓ | — | — |
| Trajectory Only | — | ✓ | — |
| Trajectory + History | ✓ | ✓ | — |
| Gen Helper + History | ✓ | — | ✓ |
| Gen Helper + Trajectory | — | ✓ | ✓ |
| CyVerACT All-In | ✓ | ✓ | ✓ |

The experiments were executed as **manually configured source variants** rather than through runtime feature flags. Before each run, the corresponding memory-related calls in the Generator and Corrector were enabled or disabled according to the target configuration. The current repository contains the cleaned integrated workflow; archived outputs preserve the completed experimental runs.

---

## Movies thesis experiment

The primary thesis experiment uses the Neo4j **Movies** knowledge graph with:

- Llama-3.1-8B-Instruct
- Qwen-2.5-7B-Instruct
- Llama-3.2-3B-Instruct

Dataset split:

- **50** memory-population questions
- **100** evaluation questions

During evaluation, `save_to_memory=False` prevents the evaluation set from being written into long-term memory.

Headline KG-valid results:

| Model | Baseline | Best memory-enabled result |
|---|---:|---:|
| Llama-3.1-8B-Instruct | 88% | 91% |
| Qwen-2.5-7B-Instruct | 73% | 83% |
| Llama-3.2-3B-Instruct | 44% | 65% |

The largest improvement is observed for the smallest model. Improvements in execution-result agreement are more limited than improvements in technical validity, so memory does not imply semantic correctness.

Figures and metric tables are stored under:

```text
CyVerACT/extended_workflow/Figures/Movies_Dataset/
```

---

## Multi-database extension

A second experiment evaluates the same memory mechanisms across five heterogeneous Neo4j schemas:

```text
northwind
companies
twitch
grandstack
recommendations
```

The final dataset contains:

- **500** evaluation questions — 100 per database
- **250** memory-population questions — 50 per database

The experiment and its figures are complete. The results are kept separate from the primary Movies experiment while their final role in the thesis narrative is reviewed.

Datasets:

```text
CyVerACT/extended_workflow/Multi_DBs_Datasets/
```

Figures:

```text
CyVerACT/extended_workflow/Figures/MultiDB_Dataset/
```

---

## Repository structure

```text
agentic-memory/
├── README.md
├── CyVerACT/
│   ├── CyVer_custom/                     # Original CyVer validators
│   ├── data/                             # Original benchmark data
│   ├── qachain_workflow/                 # Earlier/original workflow material
│   ├── extended_workflow/                # Thesis implementation
│   │   ├── Agent_Memory/
│   │   │   ├── memory_driver.py
│   │   │   └── memory_manager.py
│   │   ├── Configuration/
│   │   ├── Edges/
│   │   ├── Nodes/
│   │   │   ├── States/
│   │   │   ├── cypher_generator.py
│   │   │   ├── cyver_evaluator.py
│   │   │   ├── cypher_corrector.py
│   │   │   └── cypher_executor.py
│   │   ├── Cognee_Graphiti_Memory/       # Exploratory framework prototypes
│   │   ├── Movies_DB_Datasets/
│   │   ├── Multi_DBs_Datasets/
│   │   ├── Outputs_Evaluation/
│   │   │   ├── Movies_Experiment/
│   │   │   └── MultiDB_Experiment/
│   │   ├── Movies_Experiment_Metrics/
│   │   ├── MultiDB_Experiment_Metrics/
│   │   ├── Figures/
│   │   ├── init_memory_graph.py
│   │   ├── init_vectors.py
│   │   ├── graph.py
│   │   ├── dataset_creation.ipynb
│   │   ├── get_main_workflow_results.ipynb
│   │   ├── get_metrics_diagrams_moviesdb.ipynb
│   │   ├── get_metrics_diagrams_multidbs.ipynb
│   │   └── get_workflow_results_TEST.ipynb
│   ├── requirements.txt
│   └── requirements_3_10_12.txt
├── cognee_requirements.txt
└── zep_requirements.txt
```

`get_workflow_results_TEST.ipynb` and other legacy notebooks are preserved as historical/testing material and are not the recommended entry point for reproducing the final thesis experiments.

`Cognee_Graphiti_Memory/` contains exploratory framework integrations and is not part of the final evaluated memory architecture.

---

## Setup

### 1. Python environment

The cleaned thesis notebooks use **Python 3.11**.

Create an environment:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install the project dependencies:

```bash
pip install -r CyVerACT/requirements.txt
```

`requirements_3_10_12.txt` is retained as an earlier CyVerACT environment snapshot.

### 2. Environment variables

Create a local `.env` file. Do not commit credentials.

For the memory Neo4j database:

```env
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

For the cleaned experiment runner using OpenRouter:

```env
OPENROUTER_API_KEY=...
```

Target-database credentials for the multi-database dataset are supplied by the dataset rows used by the experiment runner.

### 3. Initialize the memory graph

From:

```bash
cd CyVerACT/extended_workflow
```

create the predefined `ErrorType → FixRule` mappings:

```bash
python init_memory_graph.py
```

Then create the three vector indexes:

```bash
python init_vectors.py
```

Both initialization steps are idempotent and can safely be rerun.

---

## Running the experiments

### Dataset preparation

```text
CyVerACT/extended_workflow/dataset_creation.ipynb
```

The notebook contains the Movies and multi-database dataset preparation logic. Existing final datasets are reused when present.

### Workflow execution

```text
CyVerACT/extended_workflow/get_main_workflow_results.ipynb
```

The cleaned runner supports both experiment families:

```python
EXPERIMENT = "movies"
```

or:

```python
EXPERIMENT = "multidb"
```

The notebook contains a separate memory-population cell and evaluation cell.

Run the memory-population cell only when initializing/rebuilding the long-term memory database. Evaluation runs use:

```python
save_to_memory=False
```

Raw workflow outputs are grouped under:

```text
Outputs_Evaluation/Movies_Experiment/
Outputs_Evaluation/MultiDB_Experiment/
```

with configuration folders such as `BASELINE`, `HISTORY_ONLY`, `TRAJECTORY_ONLY`, and `MEMORY_ALL_IN`.

Temporary `.pkl` checkpoints are stored under each experiment's `temp/` directory. The runner resumes completed rows from the corresponding `.xlsx` result file.

### Metrics and figures

Movies:

```text
CyVerACT/extended_workflow/get_metrics_diagrams_moviesdb.ipynb
```

Multi-database:

```text
CyVerACT/extended_workflow/get_metrics_diagrams_multidbs.ipynb
```

Evaluated files are stored under:

```text
Movies_Experiment_Metrics/
MultiDB_Experiment_Metrics/
```

and figures/tables under:

```text
Figures/Movies_Dataset/
Figures/MultiDB_Dataset/
```

---

## Evaluation

The evaluation separates technical validity from semantic/output agreement.

| Metric | Interpretation |
|---|---|
| KG Valid | Generated Cypher passes the CyVer validation pipeline |
| Pass@1 Output | Generated-query output matches the reference-query output under the evaluation procedure |
| Positive Jaccard Output | Output-set Jaccard similarity is greater than zero |
| Mean Jaccard Output | Average overlap between generated-query and reference-query outputs |
| BLEU | Token-level Cypher similarity |
| ROUGE-L F1 | Longest-common-subsequence similarity |
| Jaro Similarity | Character-level Cypher similarity |
| Jaccard Similarity | Token-set similarity between generated and reference Cypher |

KG validity is necessary but not sufficient for semantic correctness.

For the filtered/full-schema diagrams, schema phase is derived from the actual workflow `path`: a KG-valid result is classified as **Full Schema** when the path contains `schema_retriever`; otherwise it is classified as **Filtered Schema**.

---

## Key thesis files

| File | Role |
|---|---|
| `extended_workflow/graph.py` | Compiles the LangGraph workflow |
| `extended_workflow/Agent_Memory/memory_manager.py` | Stores and retrieves episodic/trajectory memory |
| `extended_workflow/Agent_Memory/memory_driver.py` | Connects to the Neo4j memory database |
| `extended_workflow/init_memory_graph.py` | Initializes predefined ErrorType/FixRule knowledge |
| `extended_workflow/init_vectors.py` | Creates memory vector indexes |
| `extended_workflow/Nodes/cypher_generator.py` | Initial Cypher generation and Generator Helper retrieval |
| `extended_workflow/Nodes/cyver_evaluator.py` | CyVer validation and optional attempt/error storage |
| `extended_workflow/Nodes/cypher_corrector.py` | Correction using history, trajectories, and FixRules |
| `extended_workflow/Nodes/cypher_executor.py` | Executes validator-clean Cypher |
| `extended_workflow/dataset_creation.ipynb` | Prepares/loads final datasets |
| `extended_workflow/get_main_workflow_results.ipynb` | Main Movies/MultiDB experiment runner |
| `extended_workflow/get_metrics_diagrams_moviesdb.ipynb` | Movies metrics and figures |
| `extended_workflow/get_metrics_diagrams_multidbs.ipynb` | MultiDB metrics and figures |

---

## Reproducibility notes

- The seven ablation configurations were executed as manually configured source variants, not runtime boolean switches.
- Saved experimental outputs are preserved as the archival record of the reported runs.
- The current repository is a cleaned maintained implementation and includes post-experiment code cleanup/fixes; therefore the checked-in source should not be interpreted as a byte-for-byte snapshot of every historical ablation run.
- Movies memory/evaluation splits are distinct dataset rows, but two identical natural-language question strings occur across the two subsets as separate benchmark records with different reference Cypher queries.
- The multi-database memory and evaluation files have no exact overlap on `(database_name, question)`.
- Very large output sets require care in output-based evaluation; arbitrary truncation is not equivalent to full-result Pass@1 evaluation.

---

## Project status

The Movies thesis experiment and the 500-query multi-database extension have been completed. The repository preserves the original CyVerACT material, the thesis memory extension, final datasets, evaluated metrics, and generated figures.