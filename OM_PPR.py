from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import random
import csv

# Plotting (matplotlib is standard)
import matplotlib.pyplot as plt


# ============================================================
# Workload generators (synthetic traces)
# ============================================================

def workload_locality(length: int,
                      hot_pages: List[int],
                      cold_pages: List[int],
                      hot_prob: float,
                      seed: int) -> List[int]:
    """
    Locality-heavy workload:
    - With probability hot_prob choose from hot_pages (small working set)
    - Otherwise choose from cold_pages
    """
    rng = random.Random(seed)
    refs = []
    for _ in range(length):
        if rng.random() < hot_prob:
            refs.append(rng.choice(hot_pages))
        else:
            refs.append(rng.choice(cold_pages))
    return refs


def workload_sequential_repeat(length: int,
                               cycle: List[int],
                               noise_prob: float,
                               seed: int) -> List[int]:
    """
    Sequential repeating workload:
    - Repeats a fixed cycle pattern
    - With probability noise_prob, replaces the current reference with a random element of the cycle
      (adds small realism / disturbance)
    """
    rng = random.Random(seed)
    refs = []
    i = 0
    while len(refs) < length:
        p = cycle[i % len(cycle)]
        i += 1
        if rng.random() < noise_prob:
            p = rng.choice(cycle)
        refs.append(p)
    return refs[:length]


def workload_random(length: int,
                    page_min: int,
                    page_max: int,
                    seed: int) -> List[int]:
    """Random workload (low locality)."""
    rng = random.Random(seed)
    return [rng.randint(page_min, page_max) for _ in range(length)]


# ============================================================
# Simulation results
# ============================================================

@dataclass
class SimResult:
    faults: int
    hits: int

    @property
    def refs(self) -> int:
        return self.faults + self.hits

    @property
    def fault_rate(self) -> float:
        return self.faults / self.refs if self.refs else 0.0

    @property
    def hit_ratio(self) -> float:
        return self.hits / self.refs if self.refs else 0.0

    def faults_per_1000(self) -> float:
        return (self.faults / self.refs) * 1000.0 if self.refs else 0.0


# ============================================================
# FIFO
# ============================================================

def simulate_fifo(refs: List[int], frames: int) -> SimResult:
    memory: List[int] = []
    fifo_idx = 0
    faults = 0
    hits = 0

    for p in refs:
        if p in memory:
            hits += 1
            continue

        faults += 1
        if len(memory) < frames:
            memory.append(p)
        else:
            memory[fifo_idx] = p
            fifo_idx = (fifo_idx + 1) % frames

    return SimResult(faults=faults, hits=hits)


# ============================================================
# LRU
# ============================================================

def simulate_lru(refs: List[int], frames: int) -> SimResult:
    memory: List[int] = []
    last_used: Dict[int, int] = {}
    faults = 0
    hits = 0

    for t, p in enumerate(refs):
        if p in memory:
            hits += 1
            last_used[p] = t
            continue

        faults += 1
        if len(memory) < frames:
            memory.append(p)
            last_used[p] = t
        else:
            victim = min(memory, key=lambda x: last_used.get(x, -1))
            memory[memory.index(victim)] = p
            last_used.pop(victim, None)
            last_used[p] = t

    return SimResult(faults=faults, hits=hits)


# ============================================================
# OM-PPR (Online Markov Predictive PRA) with LRU cold-start fallback
# ============================================================

def simulate_om_ppr(refs: List[int], frames: int) -> SimResult:
    """
    Online Markov-Based Predictive Page Replacement (OM-PPR):
    - Learn transition counts T[prev][cur] online.
    - On a fault, evict resident page with smallest conditional probability P(page | current).
    - If current has no transition history, fallback to LRU.
    """
    memory: List[int] = []
    faults = 0
    hits = 0

    # Markov transition counts
    T: Dict[int, Dict[int, int]] = {}

    # For LRU fallback and for tie-breaking stability
    last_used: Dict[int, int] = {}

    prev: Optional[int] = None

    def update_transition(a: int, b: int) -> None:
        row = T.setdefault(a, {})
        row[b] = row.get(b, 0) + 1

    def has_transitions(cur: int) -> bool:
        return cur in T and sum(T[cur].values()) > 0

    def cond_prob(cur: int, candidate: int) -> float:
        row = T.get(cur, {})
        total = sum(row.values())
        if total == 0:
            return 0.0
        return row.get(candidate, 0) / total

    for t, cur in enumerate(refs):
        # Learn from prev -> cur
        if prev is not None:
            update_transition(prev, cur)

        if cur in memory:
            hits += 1
            last_used[cur] = t
            prev = cur
            continue

        faults += 1

        if len(memory) < frames:
            memory.append(cur)
            last_used[cur] = t
            prev = cur
            continue

        # Eviction decision
        if has_transitions(cur):
            # Evict the resident page least likely to be referenced next (given current)
            # Tie-breaker: if equal probability, evict LRU among them (more stable results)
            probs = [(p, cond_prob(cur, p)) for p in memory]
            min_prob = min(pr for _, pr in probs)
            candidates = [p for p, pr in probs if pr == min_prob]
            victim = min(candidates, key=lambda p: last_used.get(p, -1))
        else:
            # Cold-start fallback: LRU
            victim = min(memory, key=lambda p: last_used.get(p, -1))

        memory[memory.index(victim)] = cur
        last_used.pop(victim, None)
        last_used[cur] = t
        prev = cur

    return SimResult(faults=faults, hits=hits)


# ============================================================
# Experiment runner + outputs
# ============================================================

def to_markdown_table(rows: List[dict], headers: List[str]) -> str:
    # Create markdown table
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(str(r[h]) for h in headers) + " |")
    return "\n".join(lines)


def plot_faults_vs_frames(rows: List[dict], workload_name: str, out_png: str) -> None:
    # Filter rows for the chosen workload and sort by frames
    sub = [r for r in rows if r["Workload"] == workload_name]
    sub.sort(key=lambda x: x["Frames"])

    frames = [r["Frames"] for r in sub]
    fifo_faults = [r["FIFO_Faults"] for r in sub]
    lru_faults = [r["LRU_Faults"] for r in sub]
    omp_faults = [r["OM-PPR_Faults"] for r in sub]

    plt.figure()
    plt.plot(frames, fifo_faults, marker="o", label="FIFO")
    plt.plot(frames, lru_faults, marker="o", label="LRU")
    plt.plot(frames, omp_faults, marker="o", label="OM-PPR")
    plt.xlabel("Number of Frames")
    plt.ylabel("Total Page Faults")
    plt.title(f"Page Faults vs Frames ({workload_name} Workload)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    plt.close()


def run_all() -> None:
    # ---- Tunable parameters (mention these in paper) ----
    SEED = 42
    LENGTH = 2000
    FRAME_SIZES = [3, 4, 5, 6]

    # Workload parameters
    HOT_PAGES = list(range(1, 6))           
    COLD_PAGES = list(range(6, 31))         
    HOT_PROB = 0.88

    CYCLE = [1, 2, 3, 4, 5, 6, 7, 8]
    NOISE_PROB = 0.02

    RAND_MIN, RAND_MAX = 1, 30

    # ---- Generate traces ----
    W_local = workload_locality(LENGTH, HOT_PAGES, COLD_PAGES, HOT_PROB, SEED)
    W_seq = workload_sequential_repeat(LENGTH, CYCLE, NOISE_PROB, SEED)
    W_rand = workload_random(LENGTH, RAND_MIN, RAND_MAX, SEED)

    workloads: List[Tuple[str, List[int]]] = [
        ("Locality", W_local),
        ("Sequential-Repeat", W_seq),
        ("Random", W_rand),
    ]

    # ---- Run experiments ----
    rows: List[dict] = []

    for wname, refs in workloads:
        for f in FRAME_SIZES:
            r_fifo = simulate_fifo(refs, f)
            r_lru = simulate_lru(refs, f)
            r_omp = simulate_om_ppr(refs, f)

            # Improvement vs FIFO (fault reduction)
            imp_fifo = ((r_fifo.faults - r_omp.faults) / r_fifo.faults * 100.0) if r_fifo.faults else 0.0

            rows.append({
                "Workload": wname,
                "Frames": f,
                "Refs": r_omp.refs,
                "FIFO_Faults": r_fifo.faults,
                "LRU_Faults": r_lru.faults,
                "OM-PPR_Faults": r_omp.faults,
                "OM-PPR_HitRatio": round(r_omp.hit_ratio, 4),
                "OM-PPR_Faults_per_1000": round(r_omp.faults_per_1000(), 2),
                "Imp_vs_FIFO_%": round(imp_fifo, 2),
            })

    # ---- Print a paste-friendly table ----
    headers = [
        "Workload", "Frames", "Refs",
        "FIFO_Faults", "LRU_Faults", "OM-PPR_Faults",
        "OM-PPR_HitRatio", "OM-PPR_Faults_per_1000", "Imp_vs_FIFO_%"
    ]

    print("\n=== RESULTS (paste-friendly) ===")
    print("\t".join(headers))
    for r in rows:
        print("\t".join(str(r[h]) for h in headers))

    # ---- Save CSV ----
    with open("results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    print("\nSaved: results.csv")

    # ---- Save Markdown table ----
    md = to_markdown_table(rows, headers)
    with open("results_table.md", "w", encoding="utf-8") as f:
        f.write(md + "\n")
    print("Saved: results_table.md")

    # ---- Save plots (one per workload) ----
    plot_faults_vs_frames(rows, "Locality", "faults_vs_frames_Locality.png")
    plot_faults_vs_frames(rows, "Sequential-Repeat", "faults_vs_frames_Sequential-Repeat.png")
    plot_faults_vs_frames(rows, "Random", "faults_vs_frames_Random.png")

    print("Saved: faults_vs_frames_Locality.png")
    print("Saved: faults_vs_frames_Sequential-Repeat.png")
    print("Saved: faults_vs_frames_Random.png")

    # Also print a quick note for paper parameters
    print("\n=== EXPERIMENT PARAMETERS (for Section 6.1/6.2) ===")
    print(f"Seed={SEED}, TraceLength={LENGTH}, FrameSizes={FRAME_SIZES}")
    print(f"Locality: HotPages={HOT_PAGES}, ColdPages={COLD_PAGES}, HotProb={HOT_PROB}")
    print(f"Sequential-Repeat: Cycle={CYCLE}, NoiseProb={NOISE_PROB}")
    print(f"Random: Pages=[{RAND_MIN}..{RAND_MAX}]")


if __name__ == "__main__":
    run_all()


