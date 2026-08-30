# TransCG / DFNet Reproduction

The official TransCG test split is complete locally: 52 scenes and 23,524
samples. The baseline entrypoint is the full cache-producing runner:

```bash
CUDA_VISIBLE_DEVICES=0 conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/transcg/run_dfnet_full.py \
  --official-root 透明物体/external/transcg/official \
  --dataset-root 透明物体/data/transcg/transcg \
  --checkpoint-path 透明物体/weights/transcg/checkpoint.tar \
  --output-dir 透明物体/runs/transcg/dfnet_release_test
```

`run_dfnet_native_full.sh` independently executes upstream `test.py`; it is
used to cross-check the aggregate metrics produced by the cache runner.
`evaluate_input_depth_full.py --protocol dfnet` produces the identity-input
control under exactly the same 320×240 preprocessing.

`run_dfnet_minimal.py` remains only as a synthetic debugging command and must
not be reported as a benchmark result.

See `透明物体/复现/TransCG_DFNet.md` for the complete results and provenance.
