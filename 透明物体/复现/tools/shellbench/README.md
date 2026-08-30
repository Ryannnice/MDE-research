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

TablewareNet stores `camera_image_size` as `[height, width]`. The released
processed test therefore uses `(H,W)=(240,320)`; adapters and manifests must
preserve this explicit contract. Results produced by the earlier transposed
320×240 ray grid are invalid.

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
  --output-dir 透明物体/runs/shellbench/tablewarenet_gt_per_object_hw_correct

conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/test_export_tablewarenet_shell_gt.py
```

### Same-benchmark single-depth baselines

The formal G0 comparison uses the 100-scene, four-object processed test split.
`rendered_front` is a model-free visible-surface upper bound; `masked_raw` is
the sensor-hole control. DFNet and ReMake use their released checkpoints and
released preprocessing, but TablewareNet is out of distribution for both, so
these are unified-benchmark diagnostics rather than native paper scores.

```bash
DATA=透明物体/data/tablewarenet/release/table_processed/table_object_num_4_processed/test

conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/run_tablewarenet_depth_baseline.py \
  --method rendered_front --data-root "$DATA" \
  --output-dir 透明物体/runs/shellbench/depth_rendered_front_tablewarenet_full

conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/run_tablewarenet_depth_baseline.py \
  --method masked_raw --data-root "$DATA" \
  --output-dir 透明物体/runs/shellbench/depth_masked_raw_tablewarenet_full

CUDA_VISIBLE_DEVICES=0 conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/run_tablewarenet_depth_baseline.py \
  --method dfnet --data-root "$DATA" \
  --official-root 透明物体/external/transcg/official \
  --checkpoint-path 透明物体/weights/transcg/checkpoint.tar \
  --output-dir 透明物体/runs/shellbench/depth_dfnet_tablewarenet_full

CUDA_VISIBLE_DEVICES=1 conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/run_tablewarenet_depth_baseline.py \
  --method remake --data-root "$DATA" \
  --official-root 透明物体/external/remake/official \
  --checkpoint-path 透明物体/weights/remake/checkpoint.tar \
  --relative-depth-weights \
    透明物体/weights/depth-anything-v2/depth_anything_v2_vits.pth \
  --output-dir 透明物体/runs/shellbench/depth_remake_tablewarenet_full
```

Adapt a completed axial-depth cache to the per-object ray-event contract. This
adapter intentionally uses GT object association and GT visible-front support
to isolate representation quality; it never synthesizes a back surface.

```bash
DATA=透明物体/data/tablewarenet/release/table_processed/table_object_num_4_processed/test

conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/adapt_tablewarenet_depth_baseline.py \
  --data-root "$DATA" \
  --ground-truth-root \
    透明物体/runs/shellbench/tablewarenet_gt_per_object_hw_correct \
  --prediction-root \
    透明物体/runs/shellbench/depth_dfnet_tablewarenet_full \
  --output-dir \
    透明物体/runs/shellbench/events_dfnet_tablewarenet_full
```

Pass any number of completed adapters into the frozen-candidate collision
gate with repeatable `--single-depth-root LABEL=DIR` arguments. The output
keeps optimistic and conservative unknown-space policies separate.

```bash
DATA=透明物体/data/tablewarenet/release/table_processed/table_object_num_4_processed/test

conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/shellbench/evaluate_grasp_collision_oracles.py \
  --official-root 透明物体/external/t2sqnet/official \
  --data-root "$DATA" \
  --ground-truth-root \
    透明物体/runs/shellbench/tablewarenet_gt_per_object_hw_correct \
  --prediction-objects-root \
    透明物体/runs/t2sqnet/gt_mask_test_hw_correct/objects \
  --single-depth-root \
    front=透明物体/runs/shellbench/events_rendered_front_tablewarenet_full \
  --single-depth-root \
    masked=透明物体/runs/shellbench/events_masked_raw_tablewarenet_full \
  --single-depth-root \
    dfnet=透明物体/runs/shellbench/events_dfnet_tablewarenet_full \
  --single-depth-root \
    remake=透明物体/runs/shellbench/events_remake_tablewarenet_full \
  --output-json \
    透明物体/runs/shellbench/grasp_collision_models_hw_correct.json
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
`../t2sqnet/run_t2sqnet_gt_masks.py` and
`../t2sqnet/run_t2sqnet_rgb_full.py`. The GT-mask path is a diagnostic oracle;
the official LangSAM RGB path is reported separately.

The fixed-candidate target-shell collision gate is implemented by
`evaluate_grasp_collision_oracles.py`. It compares front-only and full-event
policies on exactly the same released-planner-derived candidate set. It does not evaluate
IK, furniture, other objects, execution noise, or robot task success.

The released superellipse perimeter sampler can enter a multi-million-step
loop for pathological low-exponent predictions. The evaluator keeps normal
upstream grids exactly and uses a deterministic arc-length fallback only after
a frozen iteration cap; every fallback call and parameter set is written to
the result JSON.
