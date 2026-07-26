# ShellBench ray-event contract

This directory is the common geometry contract for the transparent-shell G0
experiment. It deliberately separates what a baseline predicts from any
downstream meshing or planner policy.

## NPZ schema

Each frame is one compressed `.npz` file with:

- `depths_m`: `float32[K,H,W]`, metric depths along the camera ray;
- `valid_mask`: `bool[K,H,W]`, whether an event exists;
- `transition_type`: `int8[K,H,W]`, `0` when the method does not predict it;
- optional `uncertainty_m`: `float32[K,H,W]`.

Valid layers are sorted front-to-back and invalid entries are trailing zeros.
Transition labels are `1=air→shell`, `2=shell→cavity`,
`3=cavity→shell`, and `4=shell→air`.

Single-depth baselines export exactly one event per pixel. They must not fill
unknown back-side geometry or label unknown space as solid. The planner stage
will compare explicitly named optimistic and conservative unknown-space
policies, rather than attributing an adapter artefact to a depth model.

## Commands

Run the dependency-light unit tests using an existing NumPy environment:

```bash
conda run -n depth4tom python \
  透明物体/复现/tools/shellbench/test_ray_events.py
```

Export DFNet/ReMake depth output (`.npy`, metres) as a single-depth event:

```bash
conda run -n depth4tom python \
  透明物体/复现/tools/shellbench/adapt_predictions.py \
  --format depth-npy --input prediction.npy --output sample.npz
```

Export one cached SeeGroup prediction:

```bash
conda run -n depth4tom python \
  透明物体/复现/tools/shellbench/adapt_predictions.py \
  --format seegroup-npz --input seegroup_cache.npz --output sample.npz
```

Generate a GT-projected representation oracle:

```bash
conda run -n depth4tom python \
  透明物体/复现/tools/shellbench/make_oracles.py \
  --ground-truth gt_events.npz --output gt_front.npz --representation front
```

Evaluate one file or matching directories. `interface_f1` includes penalties
for absent deeper events; conditional MAE/RMSE are never reported alone.

```bash
conda run -n depth4tom python \
  透明物体/复现/tools/shellbench/evaluate_ray_events.py \
  --ground-truth gt_dir --prediction pred_dir --delta-m 0.005
```

Export a TablewareNet hollow-object oracle. The command uses the official
superparaboloid implementation, which contains both inner and outer wall
surfaces; use it only for a TablewareNet processed-scene pickle, never as a
generic mesh converter.

```bash
conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/tablewarenet_shell_gt.py \
  --official-root 透明物体/external/t2sqnet/official \
  --scene-pkl <TablewareNet/test_processed/sample.pkl> \
  --view-index 0 --object-index 0 --output-npz gt_events/sample.npz
```

After installing Open3D, run the upstream-geometry integration test; it
checks one cup side ray has all four expected shell interfaces.

```bash
conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/test_tablewarenet_shell_gt.py
```

For the G0 dataset slice, use the batch exporter instead. Its default
`per_hollow_object` mode prevents occlusion between multiple objects from
being assigned a false shell/cavity transition. The companion test validates
the pickle-to-NPZ path on a minimal official Bowl.

```bash
conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/export_tablewarenet_shell_gt.py \
  --official-root 透明物体/external/t2sqnet/official \
  --data-root <TablewareNet/test_processed> \
  --output-dir 透明物体/runs/shellbench/tablewarenet_gt_per_object

conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/test_export_tablewarenet_shell_gt.py
```

## Scope and gate

This contract covers ordered ray events, not arbitrary mesh voxelization or a
robot planner. Mesh-to-event GT is dataset-specific because the distinction
between cavity and exterior free space cannot be recovered reliably from an
arbitrary mesh's intersection parity alone. TablewareNet is admitted as a
**model-induced physical-shell oracle** because its official generator exposes
the pipe's inner/outer geometry and wall parameter. TransCG meshes are not
admitted as shell-topology GT until an equivalent rim/thickness audit exists.

The released T²SQNet model can be evaluated against this contract through
`../t2sqnet/run_t2sqnet_gt_masks.py`. Its GT-mask path is a diagnostic oracle
only; it never substitutes for the RGB-segmentation result.
