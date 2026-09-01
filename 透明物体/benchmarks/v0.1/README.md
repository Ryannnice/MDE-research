# Transparent Shell Benchmark v0.1

This directory freezes the evaluation contract used before training
DepthHypothesisPack. It does not copy datasets or large predictions into Git.

## Split policy

- `LayeredDepth` real validation (300 images), Booster balanced (228 samples),
  TransCG official test (23,524 samples), and TablewareNet ShellBench (100
  scenes) are evaluation-only.
- `LayeredDepth-Syn/train` is the only v0 training source.
- No cached SeeGroup prediction from the real LayeredDepth validation set may
  be used as a training target.

## Output contract

DepthHypothesisPack v0 predicts at most four ordered metric-depth hypotheses,
with a presence probability and uncertainty for each hypothesis. Interface
transition classes, rim extraction, and a learned grasp network are deliberately
deferred until the ordered-depth gate passes.

Presence thresholds are calibrated once per layer on a held-out
LayeredDepth-Syn training partition. Real LayeredDepth and ShellBench data may
not be used to select thresholds. In the fixed planner, v0 reports its first
layer under the frozen optimistic/conservative policies and all ordered events
under fixed parity; it does not fabricate transition labels.

## Frozen evaluation tracks

1. TransCG metric depth completion: native paper/release metrics only.
2. LayeredDepth multi-layer relative depth: `layer_first` and `layer_all`.
3. ShellBench: interface/transition metrics and the fixed 7,983-candidate
   collision gate.

Numbers from these tracks must not be merged into a cross-protocol ranking.

## Verification

From the project root:

```bash
python 透明物体/benchmarks/v0.1/verify.py
python -m unittest discover -s 透明物体/benchmarks/v0.1 -p 'test_*.py'
```

The verifier checks frozen evaluator hashes, denominators, split leakage flags,
and the TablewareNet `[height,width] = [240,320]` camera convention.
