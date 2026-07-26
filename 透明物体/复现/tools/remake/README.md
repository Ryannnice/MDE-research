# ReMake Repro

Minimal command:

```bash
conda run -n remake python 透明物体/复现/tools/remake/run_remake_minimal.py \
  --out-dir 透明物体/runs/remake/minimal_synthetic
```

The script loads:

- upstream code: `透明物体/external/remake/official/`
- checkpoint: `透明物体/weights/remake/checkpoint.tar`
- outputs: `透明物体/runs/remake/`

This minimal run uses synthetic relative depth, so it verifies the ReMake core
network and checkpoint but is not an official benchmark reproduction.

Full TransCG reproduction (after the TransCG audit passes) uses the released
ReMake checkpoint and released Depth Anything V2-vits weights.  The Python
adapter preserves the upstream dataset/preprocessing/metrics and additionally
caches one metric-depth map per frame for ShellBench:

```bash
CUDA_VISIBLE_DEVICES=0 conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/remake/run_remake_full.py \
  --official-root 透明物体/external/remake/official \
  --dataset-root 透明物体/data/transcg/transcg \
  --checkpoint-path 透明物体/weights/remake/checkpoint.tar \
  --relative-depth-weights 透明物体/weights/depth-anything-v2/depth_anything_v2_vits.pth \
  --output-dir 透明物体/runs/remake/release_test
```

`run_remake_native_full.sh` is an independent, unmodified-upstream test-path
cross-check.  Neither entrypoint will label a partial data run as full.

See `透明物体/复现/ReMake.md` for the full record.
