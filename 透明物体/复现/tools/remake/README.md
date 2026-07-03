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

See `透明物体/复现/ReMake.md` for the full record.
