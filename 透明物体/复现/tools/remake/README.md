# ReMake Repro

Minimal command:

```bash
conda run -n remake python tools/repro/transparent/remake/run_remake_minimal.py \
  --out-dir runs/transparent/remake/minimal_synthetic
```

The script loads:

- upstream code: `data/external/remake/official/`
- checkpoint: `weights/transparent/remake/checkpoint.tar`
- outputs: `runs/transparent/remake/`

This minimal run uses synthetic relative depth, so it verifies the ReMake core
network and checkpoint but is not an official benchmark reproduction.

See `docs/复现/透明物体/ReMake.md` for the full record.
