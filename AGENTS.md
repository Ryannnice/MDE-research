# Repository Guidance

## Nature

This is a monocular depth estimation research workspace. Write research notes in Simplified Chinese.

## Layout

- `docs/00_A2.md`: active A2 research brief and commands.
- `a2/`: active A2 code.
- `docs/目录.md`: current documentation index.
- `docs/选题/`: current research ideas, experiment routes, and archived old idea notes.
- `docs/文献调研/`: literature notes, frontier topic briefs, and archived long-form surveys.
- `papers/`: archived PDFs, currently organized by the G1 three-era MDE trajectory.
- `tools/`: helper scripts.

Edit A2 code under `a2/`.

## A2 Verification

After changing A2 code, run:

```bash
cd a2
for f in A2_ccf_depth_skeleton A2_geo_anchor A2_eval_protocol \
         A2_baselines_postproc A2_diag_bias_var A2_marigold_bridge \
         A2_failure_slices A2_run_grid; do
  python "$f.py" || exit 1
done
```

## Research Discipline

- Do not invent experimental results. Use `待跑` until real CSV values exist.
- Keep A2 claims tied to L0/L1/L2/diag gates.
- Distinguish metric protocol from affine-invariant protocol.
- Distinguish `nfe` from `nfe_real`.
- Treat E2E-FT, ChordEdit, GeoDiff, Defocus-Marigold, AnchorD, Lotus, DepthFM, UniDepth, Metric3D, and Depth Pro as reviewer threats.

## Skills

Project-local CCFA skills are exposed through `.agents/skills -> .claude/skills`.
