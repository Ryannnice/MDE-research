# Repository Guidance

## Nature

This is a research workspace organized into three top-level themes: `MDE`, `透明物体`, and `Agentic Robot`. Write research notes in Simplified Chinese.

## Layout

- `MDE/`: monocular depth estimation research assets.
  - `MDE/目录.md`: MDE documentation index.
  - `MDE/选题/`: current MDE ideas, experiment routes, and archived old idea notes.
  - `MDE/文献调研/`: MDE literature notes, frontier topic briefs, and surveys.
  - `MDE/papers/`: MDE PDFs organized by the G1 three-era trajectory.
- `透明物体/`: transparent/non-Lambertian object depth for robotics.
  - `透明物体/透明物体单目深度估计用于机器人.md`: main transparent-object brief.
  - `透明物体/复现/`: reproduction notes and minimal runners.
  - `透明物体/external/`: external code snapshots.
  - `透明物体/pdfs/`: transparent-object PDFs.
- `Agentic Robot/`: long-horizon robot manipulation with agentic VLA/VLM loops.
  - `Agentic Robot/目录.md`: Agentic Robot documentation index.
  - `Agentic Robot/文献调研/`: Agentic Robot literature notes.
  - `Agentic Robot/papers/`: Agentic Robot PDFs.
- `.agent/skills/`: project-local CCFA skills.

Put new files under the matching top-level theme. Do not put Agentic Robot notes back under `MDE/`.

## A2 Verification

If A2 code is present and changed, run:

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

Project-local CCFA skills are under `.agent/skills/`.
