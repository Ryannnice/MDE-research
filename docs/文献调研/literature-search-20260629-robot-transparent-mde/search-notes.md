# Search Notes

Date: 2026-06-29

Mode: standard literature search feeding idea optimization.

## Safe Queries Used

- `transparent object perception robotic manipulation survey depth completion grasping`
- `transparent object depth completion grasping dataset ClearGrasp TransCG`
- `transparent object monocular depth estimation robot grasping survey`
- `ClearGrasp 3D Shape Estimation of Transparent Objects for Manipulation`
- `RGB-D Local Implicit Function for Depth Completion of Transparent Objects`
- `TransCG Transparent Object Depth Completion and Grasping`
- `ClearPose Large-scale Transparent Object Dataset and Benchmark`
- `Seeing Glass Joint Point Cloud and Depth Completion for Transparent Objects`
- `Dex-NeRF transparent object grasping NeRF`
- `Booster specular transparent surfaces depth benchmark`
- `Learning Depth Estimation for Transparent and Mirror Surfaces`
- `MOMA Monocular One-Shot Metric-Depth Alignment RGB-Based Robot Grasping`
- `Rethinking Transparent Object Grasping Monocular Depth Estimation ReMake`
- `MODEST Monocular Depth Estimation and Segmentation for Transparent Objects`
- `ClearDepth Efficient Stereo Perception of Transparent Objects for Robotic Manipulation`
- `Transparent Object Depth Completion Yifan Zhou ClearPose TransCG`
- `ASGrasp transparent object reconstruction 6-DoF grasp detection`
- `Towards Robust Monocular Depth Estimation in Non-Lambertian Surfaces`
- `LayeredDepth transparent objects multi-layer depth`
- `SeeClear Generative Opacification transparent depth`
- `SeeGroup Multi-Layer Depth Estimation transparent surfaces`
- `AISPO Affine-Invariant Shape Prior non-Lambertian robotics`

## Sources Checked

- arXiv abstract/PDF pages.
- CVF / ECVA official PDF pages.
- PMLR proceedings pages for CoRL papers.
- TU Wien repository PDF for transparent depth challenge note.
- Project pages linked by arXiv records when available.
- Local downloaded PDFs under `pdfs/`, validated via bundled Python `pypdf` page-count and first-page text extraction.

## Excluded Sources

- MDPI sources: excluded by CCFA source policy; no MDPI paper is included in the scored table.
- Search snippets without stable paper page: not used for final claims.
- `Beyond RGB-D: A Review on Improving Depth Estimation Around Glass, Mirrors, and See-through Objects`: found during search, but repository direct download failed and stable venue/source status was not verified within this pass, so it is not included in the scored table.

## Download Notes

- Created `download_manifest.tsv` as the source manifest.
- Successfully downloaded 23 PDFs into `pdfs/`.
- CVF direct link for LIDF failed; arXiv `2104.00622` was used.
- Depth4ToM institution mirror failed; arXiv `2307.15052` was used.
- SeeGroup CVF 2026 direct link failed; arXiv `2605.28735` was used.
- `pypdf` extraction confirms the downloaded PDFs are readable.

## Unknowns

- Some 2026 venue labels are taken from arXiv/project metadata. For submission writing, verify final official proceedings pages again.
- Real robot success numbers are literature-reported only; this repo has no new transparent-grasping CSV or robot logs. Any A2 claim must remain `待跑` until real results exist.
- LayeredDepth/SeeGroup introduce multi-layer depth. How to convert multi-layer depth into grasp-relevant single-surface labels remains an open task definition.
- No systematic run has compared Depth Anything V2, Metric3D, UniDepth, Depth Pro, Marigold/E2E-FT, DepthFM, AnchorD, ReMake, MOMA, AISPO, and A2 under one metric/affine protocol. This is an experiment-design need, not a completed finding.

## Handoff Notes

### For Idea Optimization

- Best seed: `transparent/grasp-relevant metric depth correction` should be framed as a failure-slice or task-grounded extension of A2, not as a generic transparent-depth model.
- Strongest close work: MOMA, ReMake, AISPO, SeeClear, SeeGroup.
- Most important distinction to preserve: A2 is about frozen prior + near-single-step + sampling-time metric anchoring, not ordinary post-hoc depth restoration.
- Most dangerous task-definition risk: transparent surfaces can be multi-layer; specify contact-surface or grasp-relevant surface.

### For Experiment Design

- Minimum offline datasets: TransCG, ClearPose, Booster, LayeredDepth.
- Minimum baselines: ClearGrasp, LIDF, ReMake, AISPO, MOMA, Depth4ToM, MODEST, SeeClear, Depth Anything V2, Metric3D, UniDepth, Depth Pro, Marigold/E2E-FT, AnchorD-like patch affine.
- Minimum metrics: full-image metric AbsRel/RMSE/δ, affine-invariant comparison, transparent-mask metric error, boundary error, no-anchor-region error, physical plausibility or invalid-grasp proxy, `nfe_real`.
- Real robot stage: only after offline L0/L1/L2/diag and transparent slice pass. Current status: `待跑`.

### For Writing

- Problem statement should not say “transparent depth is unsolved”; say “existing correction methods improve transparent-object depth, but the field lacks a clean test of whether metric correction injected during MDE/diffusion inference propagates better than equivalent post-hoc local alignment under robot-relevant transparent failure slices.”
- Claim boundary: single-layer metric depth for robot-relevant contact surface, not full optical reconstruction of all transparent layers.
- Required reviewer-threat paragraph: ClearGrasp/LIDF/TransCG/ReMake/AISPO for depth completion, MOMA for one-shot metric alignment, SeeClear/MODEST/Depth4ToM for monocular transparent MDE, LayeredDepth/SeeGroup for multi-layer depth.

### For Literature Monitoring

- Watch queries:
  - `transparent object grasping monocular depth estimation`
  - `transparent object depth completion MDE instance mask`
  - `non-Lambertian monocular metric depth robotic manipulation`
  - `multi-layer depth transparent surfaces grasping`
  - `sampling-time metric depth anchoring sparse depth diffusion depth`
- Watch datasets/projects: TransCG, ClearPose, Booster, LayeredDepth, SeeClear, SeeGroup, MOMA, ReMake, AISPO.
