# OM-PPR: Online Markov Predictive Page Replacement

A Python implementation and evaluation framework for the **Online Markov Predictive Page Replacement (OM-PPR)** algorithm, compared against traditional page replacement algorithms (FIFO and LRU).

## Overview

This project simulates and compares three page replacement algorithms:

- **FIFO** (First-In-First-Out): Replaces the oldest page in memory
- **LRU** (Least Recently Used): Replaces the least recently accessed page
- **OM-PPR** (Online Markov Predictive Page Replacement): Novel algorithm that learns page access patterns using Markov transition probabilities and evicts pages with the lowest predicted probability of future access

## Key Features

- **Online Learning**: OM-PPR builds a Markov transition model during runtime, learning patterns from the page reference stream
- **Predictive Eviction**: Instead of relying solely on historical access patterns, OM-PPR predicts future page accesses based on the current page context
- **LRU Fallback**: When no transition history exists (cold-start), the algorithm gracefully falls back to LRU
- **Multiple Workload Types**: Tests algorithms against three distinct synthetic workloads:
  - **Locality**: Hot pages accessed frequently (88% probability) vs. cold pages (12%)
  - **Sequential-Repeat**: Cyclic access pattern with minor noise
  - **Random**: Uniformly random page accesses (low locality)

## Requirements

- Python 3.7+
- matplotlib (for visualization)

Install dependencies:
```bash
pip install matplotlib
```

## Usage

Run the complete simulation and analysis:

```bash
python OM_PPR.py
```

### Output Files

The script generates several output files:

1. **results.csv**: Complete results in CSV format
2. **results_table.md**: Results formatted as a Markdown table
3. **faults_vs_frames_Locality.png**: Page faults vs frame count for Locality workload
4. **faults_vs_frames_Sequential-Repeat.png**: Page faults vs frame count for Sequential-Repeat workload
5. **faults_vs_frames_Random.png**: Page faults vs frame count for Random workload

### Console Output

The script prints:
- Tab-separated results table (paste-friendly)
- Experiment parameters used
- Confirmation of saved files

## Algorithm Details

### OM-PPR Algorithm

The OM-PPR algorithm works as follows:

1. **Online Markov Model**: Maintains a transition count matrix `T[prev][cur]` that records how often page transitions occur
2. **Conditional Probability**: On a page fault, calculates `P(candidate | current)` for each resident page
3. **Eviction Strategy**: Evicts the resident page with the **lowest** conditional probability (least likely to be needed next)
4. **Tie-Breaking**: When multiple pages have equal probability, uses LRU as a tie-breaker
5. **Cold-Start Fallback**: If the current page has no transition history, falls back to pure LRU

### Experiment Parameters

- **Trace Length**: 2,000 page references
- **Frame Sizes**: [3, 4, 5, 6]
- **Random Seed**: 42 (for reproducibility)

#### Locality Workload
- Hot Pages: 1-5 (accessed with 88% probability)
- Cold Pages: 6-30 (accessed with 12% probability)

#### Sequential-Repeat Workload
- Cycle Pattern: [1, 2, 3, 4, 5, 6, 7, 8]
- Noise Probability: 2% (random deviation from pattern)

#### Random Workload
- Page Range: 1-30
- Uniformly random distribution

## Results

The simulation measures:

- **Page Faults**: Total number of page faults for each algorithm
- **Hit Ratio**: Proportion of page references that were already in memory
- **Faults per 1000 References**: Normalized fault rate for comparison
- **Improvement vs FIFO**: Percentage reduction in page faults compared to FIFO

## Project Structure

```
.
├── OM_PPR.py                               # Main implementation and simulation
├── results.csv                             # Simulation results (CSV)
├── results_table.md                        # Simulation results (Markdown)
├── faults_vs_frames_Locality.png           # Visualization
├── faults_vs_frames_Sequential-Repeat.png  # Visualization
├── faults_vs_frames_Random.png             # Visualization
└── om_pra_full.tex                         # Research paper (LaTeX)
```

## Code Organization

The code is organized into clear sections:

1. **Workload Generators**: Functions to create synthetic page reference traces
2. **Simulation Results**: Dataclass for storing and calculating metrics
3. **Algorithm Implementations**: FIFO, LRU, and OM-PPR simulators
4. **Experiment Runner**: Main experiment logic and output generation
5. **Visualization**: Matplotlib-based plotting functions

## Performance

OM-PPR demonstrates significant improvements over FIFO in workloads with:
- High locality (predictable hot/cold page patterns)
- Sequential patterns (repeating cycles)

For random workloads with low locality, all algorithms perform similarly as there are no patterns to exploit.

