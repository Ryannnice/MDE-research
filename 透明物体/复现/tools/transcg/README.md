# TransCG / DFNet Repro

Minimal command:

```bash
conda run -n transcg python tools/repro/transparent/transcg/run_dfnet_minimal.py \
  --out-dir runs/transparent/transcg/minimal_synthetic
```

The script loads:

- upstream code: `data/external/transcg/official/`
- checkpoint: `weights/transparent/transcg/checkpoint.tar`
- outputs: `runs/transparent/transcg/`

See `docs/复现/透明物体/TransCG_DFNet.md` for the full record and real TransCG data commands.
