# DepthHypothesisPack v0/v1

This is the minimum model used after the transparent-shell representation gate.
It predicts four ordered metric-depth hypotheses, monotone presence
probabilities, and per-hypothesis uncertainty. The v0 encoder is an ImageNet
ResNet-18. The controlled v1 encoder comparison keeps the same head, loss,
split, calibration, and evaluators while replacing it with frozen DINOv2-S or
official Depth Anything V2-S features. A single full-resolution RGB refinement
layer preserves thin depth boundaries that a stride-4 decoder cannot fit.

Training uses only `LayeredDepth-Syn/train`. Real LayeredDepth validation,
Booster, TransCG, and ShellBench are evaluation-only under
`../benchmarks/v0.1/benchmark.json`.

## Prepare an auditable pilot cache

```bash
HF_HUB_DISABLE_XET=1 /root/miniconda/envs/seegroup/bin/python \
  透明物体/depth_hypothesis_pack/prepare_layereddepth_syn.py \
  --output-dir 透明物体/data/layereddepth_syn/pilot64 \
  --count 64
```

The cache stores resized RGB as uint8 and four depth layers as uint16
millimetres. It is a local generated artifact and must not be committed.

## Train and calibrate without real-evaluation leakage

```bash
PYTHONPATH=透明物体/depth_hypothesis_pack \
CUDA_VISIBLE_DEVICES=7 /root/miniconda/envs/seegroup/bin/python \
  透明物体/depth_hypothesis_pack/train.py \
  --cache-dir 透明物体/data/layereddepth_syn/train1000_v1 \
  --output-dir 透明物体/runs/depth_hypothesis_pack/<run> \
  --device cuda --epochs 20 --batch-size 4 --crop-size 192 \
  --decoder-channels 64 --train-encoder

PYTHONPATH=透明物体/depth_hypothesis_pack \
CUDA_VISIBLE_DEVICES=7 /root/miniconda/envs/seegroup/bin/python \
  透明物体/depth_hypothesis_pack/calibrate_presence.py \
  --run-dir 透明物体/runs/depth_hypothesis_pack/<run> \
  --output-json 透明物体/runs/depth_hypothesis_pack/<run>/presence_calibration.json \
  --device cuda
```

The calibration uses only the held-out indices recorded in the training run
manifest. It is frozen before running real LayeredDepth or ShellBench.

## Formal 14,800-sample v0 run

The frozen v0 run uses every released LayeredDepth-Syn training example and a
deterministic 90/10 split. Cache integrity is checked before training:

```bash
HF_HUB_DISABLE_PROGRESS_BARS=1 /root/miniconda/envs/seegroup/bin/python \
  透明物体/depth_hypothesis_pack/prepare_layereddepth_syn.py \
  --output-dir 透明物体/data/layereddepth_syn/train14800_v1 \
  --count 14800 --resize-height 288 --seed 42

/root/miniconda/envs/seegroup/bin/python \
  透明物体/depth_hypothesis_pack/verify_cache.py \
  透明物体/data/layereddepth_syn/train14800_v1

PYTHONPATH=透明物体/depth_hypothesis_pack CUDA_VISIBLE_DEVICES=7 \
  /root/miniconda/envs/seegroup/bin/python \
  透明物体/depth_hypothesis_pack/train.py \
  --cache-dir 透明物体/data/layereddepth_syn/train14800_v1 \
  --output-dir 透明物体/runs/depth_hypothesis_pack/train14800_balanced_highres_v3_seed42 \
  --device cuda --epochs 5 --batch-size 4 --crop-size 192 \
  --decoder-channels 64 --learning-rate 0.0003 \
  --encoder-learning-rate 0.00003 --weight-decay 0.0001 \
  --num-workers 0 --train-encoder --seed 42 --val-fraction 0.1
```

This completed run does not pass the main performance gate: LayeredDepth
all-quad is 32.04% and ShellBench interface F1 is 0.924%. The non-zero 20.45%
mixed-quad score is retained as representation evidence, not presented as a
performance win. Exact metrics, hashes, protocol labels, and the next decision
are recorded in
`../复现/depth_hypothesis_pack_results_2026-08-31.json` and
`../复现/DepthHypothesisPack_v0_实验记录_2026-08-31.md`.

## Controlled strong-encoder runs

The frozen DINOv2-S formal run keeps the v0 head, loss, synthetic split, and
evaluators. Unlike the fine-tuned ResNet-18 formal run, its encoder remains
frozen; the exact frozen comparison is the DINOv2-S versus Depth Anything V2-S
1,000-sample pilot below.

```bash
PYTHONPATH=透明物体/depth_hypothesis_pack CUDA_VISIBLE_DEVICES=7 \
  /root/miniconda/envs/seegroup/bin/python \
  透明物体/depth_hypothesis_pack/train.py \
  --cache-dir 透明物体/data/layereddepth_syn/train14800_v1 \
  --output-dir 透明物体/runs/depth_hypothesis_pack/train14800_dinov2s_frozen_v1_seed42 \
  --encoder dinov2_small --device cuda --epochs 5 --batch-size 4 \
  --crop-size 192 --decoder-channels 64 --learning-rate 0.0003 \
  --weight-decay 0.0001 --num-workers 0 --seed 42 --val-fraction 0.1
```

Its checkpoint improves real LayeredDepth `layer_all` quad from 32.04% to
32.91% and mixed quad from 20.45% to 25.12%, but direct TablewareNet transfer
has only 0.422% interface F1. It therefore does not pass the ShellBench gate.

Depth Anything V2-S is loaded through the official implementation and strict
official checkpoint, not through an approximate Hugging Face state conversion:

```bash
PYTHONPATH=透明物体/depth_hypothesis_pack CUDA_VISIBLE_DEVICES=7 \
  /root/miniconda/envs/seegroup/bin/python \
  透明物体/depth_hypothesis_pack/train.py \
  --cache-dir 透明物体/data/layereddepth_syn/train1000_v1 \
  --output-dir 透明物体/runs/depth_hypothesis_pack/train1000_dav2s_frozen_v1_seed42 \
  --encoder depth_anything_v2_small \
  --encoder-source-root 透明物体/external/remake/official/relat_depth_models \
  --encoder-checkpoint 透明物体/weights/depth-anything-v2/depth_anything_v2_vits.pth \
  --device cuda --epochs 20 --batch-size 4 --crop-size 192 \
  --decoder-channels 64 --learning-rate 0.0003 --weight-decay 0.0001 \
  --num-workers 0 --seed 42 --val-fraction 0.2
```

On the frozen 1,000-sample pilot it is worse than DINOv2-S in depth, front
depth, raw presence F1, and calibrated pooled F1. The predeclared pilot gate
therefore stops it before a 14,800-sample run.

## Background-depth scale diagnostic

`anchor_tablewarenet.py` fits one robust positive affine transform per view to
mask-zeroed rendered background depth, then applies it to all four hypotheses.
This is an explicit oracle-input diagnostic: the background cache was made with
the GT union object mask, so it must not be reported as a pure-RGB method.

```bash
PYTHONPATH=透明物体/depth_hypothesis_pack \
  /root/miniconda/envs/seegroup/bin/python \
  透明物体/depth_hypothesis_pack/anchor_tablewarenet.py \
  --prediction-root 透明物体/runs/depth_hypothesis_pack/tablewarenet_dinov2s_formal14800_v1_seed42 \
  --anchor-root 透明物体/runs/shellbench/depth_masked_raw_tablewarenet_full \
  --output-dir 透明物体/runs/depth_hypothesis_pack/tablewarenet_dinov2s_bganchor_v1_seed42
```

The final strong-encoder, teacher, scale, ShellBench, and planner audit is in
`../复现/DepthHypothesisPack_v1_强编码器与尺度诊断_2026-08-31.md`; exact values
are mirrored in `../复现/depth_hypothesis_pack_v1_results_2026-08-31.json`.

## Tests

```bash
PYTHONPATH=透明物体/depth_hypothesis_pack \
  /root/miniconda/envs/seegroup/bin/python -m unittest discover \
  -s 透明物体/depth_hypothesis_pack/tests -p 'test_*.py'
```
