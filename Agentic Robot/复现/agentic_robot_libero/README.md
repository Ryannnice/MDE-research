# Agentic Robot / LIBERO 复现记录

日期：2026-07-04

## 结论

已完成到“OpenVLA executor baseline 可比较，并且 VLM verifier smoke 可运行”的状态：

1. 官方 Agentic Robot 代码已拉取：`Agentic-Robot/agentic-robot`，commit `cafb8d5`。
2. 已创建 conda 环境：`ar_agentic_libero`，Python 3.10。
3. 已补齐 OpenVLA / OpenVLA-OFT / LIBERO / robosuite / MuJoCo / FlashAttention 依赖。
4. 已通过 LIBERO 仿真 smoke test：`libero_spatial` task 0 reset、render、dummy action step 正常。
5. 已完成 7B OpenVLA 最小模型 smoke eval：加载 `openvla/openvla-7b-finetuned-libero-spatial`，跑 1 个 task、1 个 episode、2 个模型 action steps，按预期 timeout。
6. 已完成 `libero_spatial` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.88 (44/50)`。
7. 已完成 `libero_object` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.82 (41/50)`。
8. 已完成 `libero_goal` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.76 (38/50)`。
9. 已完成 `libero_10` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.42 (21/50)`。
10. 已创建独立 VLM verifier 环境：`ar_agentic_libero_vlm`，保留 baseline 环境 `ar_agentic_libero` 不变。
11. 已完成 `Qwen/Qwen2.5-VL-3B-Instruct` 加载 smoke，以及 `manual_plan + Qwen verifier + OpenVLA executor` 的 1-step 集成 smoke。
12. 已在 `ar_agentic_libero_vlm` 跑 `libero_spatial` task 0 对照：原始 OpenVLA executor 指令 `1/1` 成功；当前手写 `pick/place` 分解 + verifier `0/1`，说明后续 SAP ablation 需要调 planner 子任务粒度、verifier prompt/历史帧或切换策略。
13. 已把 LRM planner 的 API key env 做成可配置参数：默认仍是 `DASHSCOPE_API_KEY`，也可显式传 `--llm_planner_api_key_env OPENAI_API_KEY`。系统原有 `OPENAI_API_KEY` / `OPENAI_BASE_URL` 组合不可用；用户提供的 OpenAI-compatible endpoint `Codex.hldragon.xyz` 已用 `gpt-5.4-mini` 验证可生成 LIBERO-Long 子任务计划。
14. 2026-07-06 继续补齐论文式 SAP 重建：`main.py` 增加 primary/fallback OpenAI-compatible planner 配置、论文式 `K=2` verifier buffer、stuck diagnosis 入口、heuristic stuck detector、lift-gripper recovery、`Rmax` recovery limit；`qwenvl.py` 修正 `put/place ... in/on ...` verifier prompt 的目标位置解析，并新增 VLM stuck diagnosis 函数。
15. 已新增不含密钥的 SAP smoke 脚本：`scripts/run_agentic_sap_smoke.sh`。默认读取 `OPENAI_API_KEY` / `OPENAI_BASE_URL`，默认使用 OpenAI-compatible API verifier；若设置 `DASHSCOPE_API_KEY` 则自动作为 planner fallback。
16. 已验证 `post_sap_patch_openvla_smoke_1step`、`post_sap_patch_vlm_smoke_1step`、`post_sap_patch_recovery_forced_smoke` 三条 smoke：baseline CLI、Qwen verifier 调用、lift recovery 分支均可运行。
17. 已验证 `scripts/run_agentic_sap_smoke.sh` 的组合入口：OpenAI-compatible planner (`gpt-5.4-mini`) 生成 `libero_10` task 0 两步 plan，随后 API VLM verifier 与 OpenVLA executor 正常进入 1-step smoke。
18. 已新增 `api_vlm.py` verifier backend。用户提供的 OpenAI-compatible endpoint 不只支持 planner，也支持 image input；`gpt-5.4-mini` 可对双视角图像队列返回 Yes/No / Stuck/StillTrying。
19. 已在 `libero_10` task 2 episode 0 跑 API verifier ablation：API verifier 可判定 `turn on the stove` 完成并切换，但纯 subtask executor 下后续 `put the moka pot on the stove` 仍 timeout；说明问题仍在 subgoal wording / verifier gate / executor state distribution，不是单纯本地 Qwen 模型不可用。
20. 新增 `--executor_instruction_mode` ablation。`original_after_first_switch` 仍失败；`original` 模式下 planner/verifier 仍按两步 subgoal 运行，但 OpenVLA executor 保持完整原始任务指令，`libero_10` task 2 episode 0 可恢复 env success `1/1`。
21. 新增 `--verify_on_env_success` 与 `--vlm_completion_confirmations`。二次确认能抑制单次 API verifier 假阳性，但 API VLM 对 `turn on stove` 和 `put moka pot on stove` 的完成判定仍不稳定，不能替代论文 LoRA fine-tuned verifier。
22. `libero_10` task 0 episode 1 多物体 basket 任务也验证了同一趋势：`--executor_instruction_mode original` 可恢复 env success `1/1`，但 API VLM verifier 对 `put the alphabet soup in the basket` 只出现一次 pending positive，终态仍判 `Not Complete`。
23. `scripts/run_agentic_sap_smoke.sh` 已将 planner 与 API VLM verifier 的模型 / endpoint 配置拆开：planner 仍默认读 `OPENAI_MODEL` / `OPENAI_BASE_URL`，API verifier 可单独用 `API_VLM_MODEL` / `API_VLM_BASE_URL` / `API_VLM_API_KEY_ENV` 指定，例如切到 DashScope OpenAI-compatible Qwen-VL endpoint。
24. 已验证 DashScope `/models` 当前可用视觉模型包括 `qwen3-vl-plus`、`qwen3-vl-flash`、`qwen-vl-plus`、`qwen-vl-max`；`qwen3-vl-plus` / `qwen-vl-plus` 在已保存 task2 早期/终态帧上能区分 `moka pot` 在炉灶旁边和在 burner 上。
25. 已跑 DashScope `qwen-plus` planner + `qwen3-vl-plus` API verifier：`executor_instruction_mode=original` 下 task2 episode0 成功且 final VLM check 判 Complete；真实 `subtask` executor 下无 recovery 和 heuristic recovery 仍失败，说明剩余主要退化仍是孤立 subgoal executor / recovery policy，而不是终态视觉判定。
26. 2026-07-07 复查官方 GitHub 页面：README 仍只描述使用 QwenVL-2.5 与 OpenVLA 评估，未给出 fine-tuned verifier 权重或数据下载；GitHub Releases 显示未发布 release。
27. 新增 `--executor_instruction_mode subtask_with_original_context` ablation；task2 episode0 仍失败，说明简单把原始目标拼到子任务 prompt 里不能修复 OpenVLA 子任务退化。
28. 已找到当前 task2 上最接近闭环的非官方配置：DashScope `qwen-plus` planner + `qwen3-vl-plus` verifier + `--executor_instruction_mode original_after_first_switch --vlm_history_length 5`，在 `t=240` 完成第二子任务 VLM confirmation，`t=255` env success。纯 `subtask + history=5` 仍失败。
29. 同一 best-current 配置迁移到 `libero_10` task0 episode1 仍失败：纯 first-subtask 执行无法完成 basket 多物体任务；即使 `executor_instruction_mode=original` 恢复 env success，`qwen3-vl-plus` + history=5 仍对 `put alphabet soup in basket` 终态漏判。
30. 已给 API / local Qwen verifier 加入 LIBERO 物体外观 hint 与 basket/container 目标关系 hint；task0 episode1 在 `executor_instruction_mode=original --vlm_history_length 5` 下现在可完成两步 VLM plan confirmation：`t=130` alphabet soup Complete，`t=240` tomato sauce Complete，`t=272` env success。
31. 新增 `--llm_planner_style {outcome,paper_atomic}`。`paper_atomic` 按论文 SAP skill library 风格生成 `pick up` / `place` / `turn on` 等原子技能，并新增后处理把 `turn on stove` / `place moka pot on stove` 规范成更接近 LIBERO/OpenVLA 训练分布的 `turn on the stove` / `place the moka pot on the stove`。
32. 论文式 `paper_atomic + subtask executor` task2 对照失败：DashScope VLM 可切换 turn on 和 pick up，但最后 `place moka pot on stove` timeout。`paper_atomic + original_after_first_switch + history=5` 则完成三步 VLM plan confirmation 并 env success，进一步说明当前开源 OpenVLA 对孤立 place subgoal 的执行分布不稳。
33. 新增诊断-only `--vlm_verifier_backend libero_oracle`，直接调用 LIBERO simulator predicates，不作为可报告 SAP 指标，只用于隔离 verifier 误判和 executor 退化。oracle backend 会自动 unwrap `OffScreenRenderEnv.env`，并支持 `turnon/open/close/in/on` 谓词及近似 `pick up` 检查。
34. oracle 诊断确认 OpenVLA 对 atomic subtask wording 非常敏感：`turn on stove` 520 steps 未触发 `Turnon`，而 `turn on the stove` 在 `t=110` 触发。带冠词三步 plan + 真实 `subtask` executor 可完成 `turn on` (`t=110`) 和 `pick up` (`t=180`)，但 `place the moka pot on the stove` 仍 timeout；同一 plan + `original_after_first_switch` 在 `t=289` env success，final oracle check 判 `Complete`。
35. 新增 `--executor_instruction_mode subtask_with_progress_context`。两步 outcome plan `turn on the stove -> put the moka pot on the stove` 在纯 `subtask` 下仍 timeout；改用 progress-context executor 后，`t=110` 完成第一步，`t=257` env success，final oracle check 对第二步判 `Complete`。这说明相比直接恢复完整原始指令，显式“已完成步骤 + 当前步骤”的执行上下文是更接近 SAP 的可行修复方向。
36. 本地 Qwen2.5-VL verifier + progress-context executor 在 task2 episode0 上形成非 oracle 闭环：`t=110` Qwen 确认 `turn on the stove`，`t=190` Qwen 确认 `put the moka pot on the stove` 并完成 plan，`t=290` env success。该结果使用开源本地 Qwen verifier，不依赖 API。
37. 同一 progress-context 配置迁移到 task0 episode1 仍失败：本地 Qwen 对 `put the alphabet soup in the basket` 始终判 `No` 到 timeout；oracle verifier 同样未确认第一步，说明该 case 主要是 OpenVLA executor/subgoal policy 没完成 basket 第一子任务，而不是 Qwen 视觉漏判。
38. 为 task0 继续测试了更贴近 LIBERO-object 训练表述的 `pick up the alphabet soup and place it in the basket`，并把 oracle / Qwen / API verifier parser 改为按最终 placement 验收这种复合短句；oracle ablation 仍未确认第一步。`subtask_with_original_context` 也未确认第一步，进一步说明 task0 不是单纯 parser、动词或上下文格式问题。
39. task0 episode1 继续排除简单 object-order 解释：把两步 plan 换成 `put the tomato sauce in the basket -> put the alphabet soup in the basket`，progress-context + oracle verifier 仍在第一步 `t=530` timeout，env success `0/1`。
40. task0 episode1 的 oracle sanity check 通过：executor 始终使用原始完整任务，verifier 仍按两步 basket subgoal 检查时，oracle 在 `t=150` 确认 alphabet soup，env success 后 terminal-frame final check 在 `t=272` 确认 tomato sauce，成功率 `1/1`。这说明 oracle/parser 能识别 basket 子目标，失败点确实是孤立子任务执行策略。
41. 扩展 diagnostic oracle 和 VLM prompt hints：oracle 现在能解析 `bottom drawer of the cabinet` -> `white_cabinet_1_bottom_region`、`back compartment of the caddy` -> `desk_caddy_1_back_contain_region`；API / local Qwen verifier prompt 也补了 book、black bowl、drawer、caddy target hints，并放宽 pick-up gate 对手爪遮挡的描述。
42. task3 episode1（black bowl -> bottom drawer -> close）不是可靠正例：progress-context + oracle 在 `t=170` 确认 bowl in drawer，但 close drawer 到 `t=430` timeout；original executor + oracle 用 520-step cap 也 timeout；同 task/episode 的纯 OpenVLA baseline control 也 timeout，因此不再用它证明 SAP generalization。
43. task5 episode0（book -> back caddy compartment）给出第二个 oracle-positive progress-context case：oracle 在 `t=70` 确认 `pick up the book`，env success `t=200`，terminal final oracle check 判 `place the book in the back compartment of the caddy` Complete。
44. task5 local Qwen2.5-VL verifier 仍不可靠：两步 pick/place plan 下严格 pick-up prompt 和放宽 pick-up prompt 都始终 `No` 到 timeout；单一 composite subtask 能让 executor env success `t=174`，但 final Qwen verifier 仍判 `Not Complete`。这进一步支持论文 fine-tuned verifier / 更强 API VLM 是完整 SAP 复现的关键条件。
45. DashScope OpenAI-compatible `/models` 当前列出 `qwen3-vl-plus`、`qwen3-vl-flash`、`qwen-vl-plus`、`qwen-vl-max` 等 VLM；API key 只通过单次 shell env 传入，未写入文件。
46. task5 用 DashScope `qwen3-vl-plus` 复跑：`vlm_history_length=5` 能在 `t=70` 确认 `pick up the book`，但仍漏判 caddy placement；抽取成功轨迹终帧后发现 black book 与 dark caddy 视觉上融合，补充 caddy hint + `vlm_history_length=1` 后，`t=70` 确认 pick-up，`t=110` 确认 caddy placement，`t=217` env success。
47. task2 用 DashScope `qwen3-vl-plus` + progress-context 形成 API VLM 闭环：两步 plan `turn on the stove -> put the moka pot on the stove` 在 `t=110` 确认第一步，`t=250` 确认第二步并完成 plan，`t=263` env success。这补上了此前因当前 shell OpenAI token 401 而缺失的 API progress-context 证据。
48. 已跑通两个不使用 `MANUAL_PLAN` 的 end-to-end SAP-style 配置：task2 由 DashScope `qwen-plus` planner 生成 `turn on the stove -> put the moka pot on the stove`，`qwen3-vl-plus` verifier 在 `t=110/t=240` 确认两步，`t=262` env success；task5 planner 保留单一 outcome-level transfer，`qwen3-vl-plus` verifier 在 `t=100` 确认完成，`t=172` env success。
49. 2026-07-07 再次查官方远端：`git ls-remote` 仍只有 `main@cafb8d5`，GitHub releases/tags API 均返回 `count 0`，没有官方 verifier 权重 / release 包。当前 shell 的 OpenAI-compatible token 对 API VLM 返回 401；DashScope API 可作为可复跑的 OpenAI-compatible VLM backend。

当前可比较指标仍是 OpenVLA executor baseline，不是论文完整 SAP 指标。本地已给 `main.py` 增加可选 planner / verifier / recovery 开关；默认仍保持 executor baseline 行为。OpenAI-compatible planner、API VLM / Qwen verifier、oracle diagnostic verifier 和 recovery 路径已跑通 smoke；DashScope `qwen3-vl-plus` 是目前最强的可用 API verifier：在 task2 progress-context 上完成两步 VLM confirmation + env success，在 task5 上需要 `vlm_history_length=1` 才能避免历史帧干扰并完成 caddy placement confirmation。当前最接近论文 PEV/SAP 的可复跑结果是 `qwen-plus` planner + `qwen3-vl-plus` verifier + progress-context executor，在 task2 和 task5 单 episode 上均不依赖 manual plan 跑通。新增 `paper_atomic` planner 可生成论文式原子 skill sequence，并已修复 bare noun phrasing，但真实 subtask executor 仍在 task2 atomic `place the moka pot on the stove` 和 task0 first-subtask basket 执行上失败。task0 oracle 在多种拆法下失败，task5 local Qwen 对 pick-up/caddy placement 仍漏判，task3 单 episode baseline control 也不稳定。官方仓库目前未发布 fine-tuned verifier artifact；完整 SAP 指标仍需要 fine-tuned verifier 或等价重建，以及完整 LIBERO protocol ablation。

## 目录

```text
agentic_robot_libero/
  README.md
  environment_ar_agentic_libero.yml
  environment_ar_agentic_libero_vlm.yml
  pip_freeze_ar_agentic_libero.txt
  pip_freeze_ar_agentic_libero_vlm.txt
  patches/agentic_robot_main_smoke.patch
  tools/smoke_libero_env.py
  data/libero_config/config.yaml
  data/logs/
  data/hf_cache/              # ignored, HF checkpoint cache
  data/libero_datasets/       # ignored
  repos/                      # ignored, cloned upstream repos
```

## 环境删除后的恢复命令

2026-07-05 已按下面流程重建并验证 `ar_agentic_libero`。不要只执行 `conda env create -f environment_ar_agentic_libero.yml`：该文件来自 `conda env export`，会把 Git 安装的 `dlimp` 记录成 PyPI 上不存在的 `dlimp==0.0.1`，导致 pip 阶段失败。

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"

apt-get update
apt-get install -y libosmesa6 libegl1 libopengl0 libgl1

conda env remove -n ar_agentic_libero || true
conda create -y -n ar_agentic_libero -c defaults -c conda-forge \
  python=3.10.20 pip=26.1.2 setuptools=82.0.1 wheel=0.47.0 \
  packaging=26.0 mesalib=25.3.5

/root/miniconda/envs/ar_agentic_libero/bin/python -m pip install \
  --extra-index-url https://download.pytorch.org/whl/cu121 \
  "torch==2.2.0+cu121" "torchvision==0.17.0+cu121" "torchaudio==2.2.0+cu121"

REQ="$REPRO_ROOT/pip_freeze_ar_agentic_libero.txt"
/root/miniconda/envs/ar_agentic_libero/bin/python -m pip install \
  --extra-index-url https://download.pytorch.org/whl/cu121 \
  -r <(grep -v -E '^(torch==|torchvision==|torchaudio==|flash-attn==|-e git\+)' "$REQ")

/root/miniconda/envs/ar_agentic_libero/bin/python -m pip install --no-deps \
  -e "$REPRO_ROOT/repos/LIBERO" \
  -e "$REPRO_ROOT/repos/agentic-robot" \
  -e "$REPRO_ROOT/repos/openvla-oft"

/root/miniconda/envs/ar_agentic_libero/bin/python -m pip install \
  --no-build-isolation "flash-attn==2.5.5"
```

恢复后至少运行：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"

/root/miniconda/envs/ar_agentic_libero/bin/python -m pip check

LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
MUJOCO_GL=osmesa \
PYOPENGL_PLATFORM=osmesa \
TOKENIZERS_PARALLELISM=false \
TF_CPP_MIN_LOG_LEVEL=3 \
WANDB_MODE=disabled \
/root/miniconda/envs/ar_agentic_libero/bin/python "$REPRO_ROOT/tools/smoke_libero_env.py"
```

本次恢复后已验证：

- `/root/miniconda/envs/ar_agentic_libero/bin/python -m pip check`：通过。
- `python -m py_compile experiments/robot/libero/main.py experiments/robot/libero/qwenvl.py experiments/robot/libero/ds.py`：通过。
- `tools/smoke_libero_env.py`：输出 `SMOKE_LIBERO_OK`。
- OpenVLA 7B 最小 smoke：`libero_spatial` task 0、1 trial、`--max_steps_override 1`，模型加载与 1 step 推理通过，按预期 timeout；日志为 `data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-06_08_30--restore_smoke_1task_1step.txt`。

### VLM verifier 环境

不要在 `ar_agentic_libero` 里直接升级 `transformers`。OpenVLA baseline 环境固定为 `transformers==4.40.1` / `tokenizers==0.19.1`；Qwen2.5-VL verifier 另用克隆环境：

```bash
conda create -y -n ar_agentic_libero_vlm --clone ar_agentic_libero
/root/miniconda/envs/ar_agentic_libero_vlm/bin/python -m pip install "transformers==4.51.3"
```

已导出环境记录：

```text
environment_ar_agentic_libero_vlm.yml
pip_freeze_ar_agentic_libero_vlm.txt
```

验证状态：

- `/root/miniconda/envs/ar_agentic_libero/bin/python`：`transformers 4.40.1`，`tokenizers 0.19.1`。
- `/root/miniconda/envs/ar_agentic_libero_vlm/bin/python`：`transformers 4.51.3`，`tokenizers 0.21.4`。
- `ar_agentic_libero_vlm` 可 import `Qwen2_5_VLForConditionalGeneration` 和 `qwen_vl_utils.process_vision_info`。
- `Qwen/Qwen2.5-VL-3B-Instruct` 已下载到 `data/hf_cache`，加载和最小 `check_completion_with_qwen_vl()` 生成路径通过。
- `ar_agentic_libero_vlm` 的 `pip check` 会报告 OpenVLA 元数据版本冲突，这是预期的：该环境只用于 verifier / SAP smoke；完整 executor baseline 仍使用 `ar_agentic_libero`。

## 已复现结果

### 1. LIBERO 环境 smoke test

命令：

```bash
conda run -n ar_agentic_libero python \
  "/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero/tools/smoke_libero_env.py"
```

关键输出：

```json
{
  "status": "SMOKE_LIBERO_OK",
  "suite": "libero_spatial",
  "task_id": 0,
  "agentview_image_shape": [128, 128, 3],
  "processed_image_shape": [128, 128, 3],
  "reward": 0.0,
  "done": false
}
```

### 2. OpenVLA 7B 最小模型 smoke eval

首次运行已下载 Hugging Face checkpoint 到：

```text
/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero/data/hf_cache
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
    --task_suite_name libero_spatial \
    --center_crop True \
    --num_trials_per_task 1 \
    --start_task_id 0 \
    --max_tasks 1 \
    --max_steps_override 2 \
    --save_frames False \
    --run_id_note smoke_1task_2steps \
    --local_log_dir "$REPRO_ROOT/data/logs" \
    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

实际结果：

```text
Loaded model: OpenVLAForActionPrediction
Task: pick up the black bowl between the plate and the ramekin and place it on the plate
[t=12] Episode TIMEOUT.
Total Success Rate: 0.00 (0/1)
eval_libero total_time: 905.43 seconds
```

这里的 timeout 是预期结果，因为 `--max_steps_override 2` 只用于验证模型推理和环境 step，不用于衡量成功率。

日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_04-08_37_38--smoke_1task_2steps.txt
```

### 3. OpenVLA 7B `libero_spatial` 完整 executor baseline

运行时间：2026-07-04 18:09:46 到 18:52:18 UTC
配置：`libero_spatial`，10 tasks，`--num_trials_per_task 5`，无 VLM verifier，`save_frames=False`
模型：`openvla/openvla-7b-finetuned-libero-spatial`

结果：

```text
Total Success Rate: 0.88 (44/50)
eval_libero total_time: 2551.87 seconds
```

逐 task 成功率：

| task_id | success | task |
|---:|---:|---|
| 0 | 5/5 | pick up the black bowl between the plate and the ramekin and place it on the plate |
| 1 | 5/5 | pick up the black bowl next to the ramekin and place it on the plate |
| 2 | 4/5 | pick up the black bowl from table center and place it on the plate |
| 3 | 4/5 | pick up the black bowl on the cookie box and place it on the plate |
| 4 | 3/5 | pick up the black bowl in the top drawer of the wooden cabinet and place it on the plate |
| 5 | 5/5 | pick up the black bowl on the ramekin and place it on the plate |
| 6 | 5/5 | pick up the black bowl next to the cookie box and place it on the plate |
| 7 | 5/5 | pick up the black bowl on the stove and place it on the plate |
| 8 | 3/5 | pick up the black bowl next to the plate and place it on the plate |
| 9 | 5/5 | pick up the black bowl on the wooden cabinet and place it on the plate |

日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_04-18_09_46--full_executor_baseline_5trials.txt
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
    --task_suite_name libero_spatial \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --run_id_note full_executor_baseline_5trials \
    --local_log_dir "$REPRO_ROOT/data/logs" \
    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

### 4. OpenVLA 7B `libero_object` 完整 executor baseline

运行时间：2026-07-04 19:55:12 到 20:45:08 UTC
配置：`libero_object`，10 tasks，`--num_trials_per_task 5`，无 VLM verifier，`save_frames=False`
模型：`openvla/openvla-7b-finetuned-libero-object`

结果：

```text
Total Success Rate: 0.82 (41/50)
eval_libero total_time: 2995.33 seconds
```

逐 task 成功率：

| task_id | success | task |
|---:|---:|---|
| 0 | 3/5 | pick up the alphabet soup and place it in the basket |
| 1 | 4/5 | pick up the cream cheese and place it in the basket |
| 2 | 4/5 | pick up the salad dressing and place it in the basket |
| 3 | 3/5 | pick up the bbq sauce and place it in the basket |
| 4 | 4/5 | pick up the ketchup and place it in the basket |
| 5 | 4/5 | pick up the tomato sauce and place it in the basket |
| 6 | 4/5 | pick up the butter and place it in the basket |
| 7 | 5/5 | pick up the milk and place it in the basket |
| 8 | 5/5 | pick up the chocolate pudding and place it in the basket |
| 9 | 5/5 | pick up the orange juice and place it in the basket |

日志：

```text
data/logs/PEV_V1-EVAL-libero_object-openvla-2026_07_04-19_55_12--full_executor_baseline_5trials.txt
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-object \
    --task_suite_name libero_object \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --run_id_note full_executor_baseline_5trials \
    --local_log_dir "$REPRO_ROOT/data/logs" \
    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

### 5. OpenVLA 7B `libero_goal` 完整 executor baseline

运行时间：2026-07-04 20:46:45 到 21:36:24 UTC
配置：`libero_goal`，10 tasks，`--num_trials_per_task 5`，无 VLM verifier，`save_frames=False`
模型：`openvla/openvla-7b-finetuned-libero-goal`

结果：

```text
Total Success Rate: 0.76 (38/50)
eval_libero total_time: 2978.27 seconds
```

逐 task 成功率：

| task_id | success | task |
|---:|---:|---|
| 0 | 2/5 | open the middle drawer of the cabinet |
| 1 | 5/5 | put the bowl on the stove |
| 2 | 5/5 | put the wine bottle on top of the cabinet |
| 3 | 3/5 | open the top drawer and put the bowl inside |
| 4 | 5/5 | put the bowl on top of the cabinet |
| 5 | 1/5 | push the plate to the front of the stove |
| 6 | 3/5 | put the cream cheese in the bowl |
| 7 | 5/5 | turn on the stove |
| 8 | 5/5 | put the bowl on the plate |
| 9 | 4/5 | put the wine bottle on the rack |

日志：

```text
data/logs/PEV_V1-EVAL-libero_goal-openvla-2026_07_04-20_46_45--full_executor_baseline_5trials.txt
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-goal \
    --task_suite_name libero_goal \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --run_id_note full_executor_baseline_5trials \
    --local_log_dir "$REPRO_ROOT/data/logs" \
	    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

### 6. OpenVLA 7B `libero_10` 完整 executor baseline

运行时间：2026-07-04 21:37:39 到 23:22:25 UTC
配置：`libero_10`，10 tasks，`--num_trials_per_task 5`，无 VLM verifier，`save_frames=False`
模型：`openvla/openvla-7b-finetuned-libero-10`

结果：

```text
Total Success Rate: 0.42 (21/50)
eval_libero total_time: 6285.14 seconds
```

逐 task 成功率：

| task_id | success | task |
|---:|---:|---|
| 0 | 2/5 | put both the alphabet soup and the tomato sauce in the basket |
| 1 | 4/5 | put both the cream cheese box and the butter in the basket |
| 2 | 2/5 | turn on the stove and put the moka pot on it |
| 3 | 2/5 | put the black bowl in the bottom drawer of the cabinet and close it |
| 4 | 1/5 | put the white mug on the left plate and put the yellow and white mug on the right plate |
| 5 | 4/5 | pick up the book and place it in the back compartment of the caddy |
| 6 | 2/5 | put the white mug on the plate and put the chocolate pudding to the right of the plate |
| 7 | 2/5 | put both the alphabet soup and the cream cheese box in the basket |
| 8 | 2/5 | put both moka pots on the stove |
| 9 | 0/5 | put the yellow and white mug in the microwave and close it |

日志：

```text
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_04-21_37_39--full_executor_baseline_5trials.txt
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-10 \
    --task_suite_name libero_10 \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --run_id_note full_executor_baseline_5trials \
    --local_log_dir "$REPRO_ROOT/data/logs" \
    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

### 7. VLM verifier / manual plan 集成 smoke

运行时间：2026-07-05 08:26:43 UTC
配置：`libero_spatial` task 0，1 trial，`--max_steps_override 1`，启用 `--enable_vlm_verifier True`，使用手写 plan 避开缺失的 DashScope planner key。
模型：

- Executor：`openvla/openvla-7b-finetuned-libero-spatial`
- Verifier：`Qwen/Qwen2.5-VL-3B-Instruct`

结果：集成路径跑通，Qwen verifier 在 `t=10` 被调用并返回 `Not Complete`；episode 按预期 timeout。

```text
Plan Source: manual_plan
Plan: ['pick up the black bowl', 'place the black bowl on the plate']
[t=10] VLM Check Start: 'pick up the black bowl' (Queue size: 1)
[t=10] VLM Check Result: Not Complete
Total Success Rate: 0.00 (0/1)
```

日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-08_26_43--vlm_env_manual_plan_verifier_smoke_1step.txt
```

同环境下还验证了不启用 verifier 的 OpenVLA 1-step smoke：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-08_25_39--vlm_env_openvla_smoke_1step.txt
```

复跑命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
HF_HOME="$REPRO_ROOT/data/hf_cache" \
LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
MUJOCO_GL=osmesa \
PYOPENGL_PLATFORM=osmesa \
TOKENIZERS_PARALLELISM=false \
TF_CPP_MIN_LOG_LEVEL=3 \
WANDB_MODE=disabled \
/root/miniconda/envs/ar_agentic_libero_vlm/bin/python experiments/robot/libero/main.py \
  --model_family openvla \
  --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
  --task_suite_name libero_spatial \
  --center_crop True \
  --num_trials_per_task 1 \
  --max_tasks 1 \
  --max_steps_override 1 \
  --save_frames False \
  --local_log_dir "$REPRO_ROOT/data/logs" \
  --run_id_note vlm_env_manual_plan_verifier_smoke_1step \
  --enable_vlm_verifier True \
  --manual_plan "pick up the black bowl||place the black bowl on the plate"
```

### 8. VLM 环境 task 0 对照

运行时间：2026-07-05 08:29:56 到 08:33:52 UTC
suite：`libero_spatial` task 0，1 trial。

结果：

| 配置 | 结果 | 说明 |
|---|---:|---|
| `ar_agentic_libero_vlm`，原始 task 指令，verifier 关闭 | `1/1` | `t=91` env success |
| `ar_agentic_libero_vlm`，原始 task 指令，verifier 开启 | `1/1` | Qwen 从 `t=10` 到 `t=90` 检查均为 `Not Complete`，但不改变 executor 指令，`t=91` env success |
| `ar_agentic_libero_vlm`，手写 `pick/place` plan，verifier 开启 | `0/1` | verifier 从 `t=10` 到 `t=225` 均为 `Not Complete`，未切换到 place |
| `ar_agentic_libero_vlm`，手写 `pick/place` plan，`--vlm_history_length 5 --verify_frequency 10` | `0/1` | verifier 从 `t=10` 到 `t=220` 均为 `Not Complete`，历史帧没有解决切换问题 |

关键日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-08_33_06--vlm_env_executor_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-09_00_06--vlm_env_original_instruction_verifier_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-08_29_56--vlm_env_manual_plan_verifier_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-09_05_27--vlm_env_manual_plan_verifier_task0_1trial_hist5_freq10.txt
```

结论：新版 `transformers` verifier 环境没有破坏 OpenVLA executor 的 task 0 行为；当前回归来自朴素手写 plan / verifier 判断策略。继续做 SAP ablation 前，应优先处理：

- planner 生成的 subtask 是否保留足够空间关系，例如 `between the plate and the ramekin`。
- verifier prompt 对 `pick up` 的完成条件是否过严；如果对象已经被放下，当前 prompt 仍可能判定 pick 未完成。
- 子任务切换时机和 verifier prompt。单独把 `--vlm_history_length` 从 1 提到 5、把 `--verify_frequency` 从 5 调到 10 仍未触发 `pick up` 完成。

### 9. LRM planner API key env smoke

运行时间：2026-07-05 09:03:12 UTC
配置：`ar_agentic_libero`，`libero_spatial` task 0，1 trial，`--max_steps_override 1`，启用 `--use_llm_planner True`，显式传 `--llm_planner_api_key_env OPENAI_API_KEY`、`--llm_planner_base_url https://api.openai.com/v1`、`--llm_planner_model gpt-4o-mini`。

结果：当前 `OPENAI_API_KEY` 为无效 token，planner 返回空 plan，主流程按预期 fallback 到原始任务指令并完成 1-step timeout。

```text
LLM Planner Enabled: True
LLM Planner API Key Env: OPENAI_API_KEY
Warning: LLM planner returned no steps.
Plan Source: original_task
Total Success Rate: 0.00 (0/1)
```

日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-09_03_12--planner_openai_invalid_key_fallback_smoke_1step.txt
```

复跑命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
HF_HOME="$REPRO_ROOT/data/hf_cache" \
LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
MUJOCO_GL=osmesa \
PYOPENGL_PLATFORM=osmesa \
TOKENIZERS_PARALLELISM=false \
TF_CPP_MIN_LOG_LEVEL=3 \
WANDB_MODE=disabled \
/root/miniconda/envs/ar_agentic_libero/bin/python experiments/robot/libero/main.py \
  --model_family openvla \
  --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
  --task_suite_name libero_spatial \
  --center_crop True \
  --num_trials_per_task 1 \
  --max_tasks 1 \
  --max_steps_override 1 \
  --save_frames False \
  --local_log_dir "$REPRO_ROOT/data/logs" \
  --run_id_note planner_openai_invalid_key_fallback_smoke_1step \
  --use_llm_planner True \
  --llm_planner_api_key_env OPENAI_API_KEY \
  --llm_planner_base_url https://api.openai.com/v1 \
  --llm_planner_model gpt-4o-mini
```

### 10. DashScope `qwen-plus` planner / SAP 小规模 ablation

2026-07-05 使用 DashScope OpenAI-compatible endpoint 验证 LRM planner 路径：

```text
base_url https://dashscope.aliyuncs.com/compatible-mode/v1
model qwen-plus
api_key_env DASHSCOPE_API_KEY
```

API smoke 结果：

| task | parsed plan |
|---|---|
| `pick up the black bowl between the plate and the ramekin and place it on the plate` | `['pick up the black bowl between the plate and the ramekin and place it on the plate']` |
| `put both the alphabet soup and the tomato sauce in the basket` | `['put the alphabet soup in the basket', 'put the tomato sauce in the basket']` |
| `turn on the stove and put the moka pot on it` | `['turn on the stove', 'put the moka pot on the stove']` |

代码调整：

1. `ds.py` 的 planner prompt 改为 outcome-level subgoals；单对象 transfer 保留原始 wording，避免丢掉 source location / spatial relation。
2. `qwenvl.py` 的 verifier prompt 识别 `put ... in/on ...`，与 `place ... in/on ...` 一样按放置完成条件判断。
3. `main.py` 增加 `--start_episode_id`，用于对齐指定初始状态做小规模 ablation；默认值为 `0`，不改变完整 baseline 行为。

实测结果：

| 配置 | 任务 / 初始状态 | plan | 结果 | 结论 |
|---|---|---|---:|---|
| `qwen-plus planner + Qwen verifier + OpenVLA`，旧 atomic prompt | `libero_spatial` task 0 episode 0 | `pick up black bowl` -> `place black bowl on plate` | `0/1` | atomic `pick/place` 会破坏 OpenVLA executor |
| `qwen-plus planner + Qwen verifier + OpenVLA`，outcome prompt 但丢 source relation | `libero_spatial` task 0 episode 0 | `put the black bowl on the plate` | `0/1` | source/spatial wording 不能丢 |
| `qwen-plus planner + Qwen verifier + OpenVLA`，保留单对象原始 wording | `libero_spatial` task 0 episode 0 | 原始完整任务 | `1/1`，`t=91` env success | LRM planner 路径可用，且不破坏单步 executor |
| `qwen-plus planner + Qwen verifier + OpenVLA`，multi-object split | `libero_10` task 0 episode 0 | `put alphabet soup in basket` -> `put tomato sauce in basket` | `0/1` | episode 0 原始 baseline 也失败，不能单独说明 SAP 退化 |
| `qwen-plus planner + Qwen verifier + OpenVLA`，multi-object split | `libero_10` task 0 episode 1 | `put alphabet soup in basket` -> `put tomato sauce in basket` | `0/1` | 同一初始状态原始 baseline 成功，说明当前 split/verifier 策略会退化 |
| 原始完整任务 + Qwen verifier + OpenVLA | `libero_10` task 0 episode 1 | 原始完整任务 | `1/1`，`t=272` env success | VLM 环境本身未破坏 executor，退化来自子任务拆分/切换策略 |
| 手工 object-level split + Qwen verifier + OpenVLA | `libero_10` task 1 episode 0 | `put cream cheese box in basket` -> `put butter in basket` | `1/1`，`t=321` env success | verifier 未确认第一步完成，但 executor 在第一条子任务下仍完成整任务；说明部分多物体任务可被 executor 泛化兜住 |
| 手工 state/action split + Qwen verifier + OpenVLA | `libero_10` task 2 episode 0 | `turn on stove` -> `put moka pot on stove` | `0/1` | verifier 在 `t=120` 成功切到第二步，但最终 timeout；同一初始状态原始 baseline 成功，说明切换时机 / 子任务 wording / verifier 策略仍会退化 |
| `qwen-plus planner + Qwen verifier + OpenVLA` | `libero_10` task 2 episode 0 | `turn on stove` -> `put moka pot on stove` | `0/1` | 百炼 planner 真实路径生成与手工相同的 plan；verifier 在 `t=120` 切换，最终 timeout，确认问题不在 API fallback |

新增日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-16_27_14--planner_qwen_plus_verifier_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-16_30_27--planner_qwen_plus_outcome_verifier_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-16_33_54--planner_qwen_plus_preserve_single_verifier_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_05-16_35_33--planner_qwen_plus_verifier_libero10_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_05-16_40_51--planner_qwen_plus_verifier_libero10_task0_ep1_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_05-16_45_06--original_instruction_verifier_libero10_task0_ep1_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_05-17_56_31--manual_split_verifier_libero10_task1_ep0_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_05-17_59_59--manual_split_verifier_libero10_task2_ep0_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_05-18_18_35--planner_qwen_plus_verifier_libero10_task2_ep0_1trial.txt
```

结论：DashScope `qwen-plus` planner 已可用，之前的 LRM API key 阻塞解除；但当前 zero-shot Qwen verifier 与 OpenVLA 子任务拆分仍不能代表论文完整 SAP。新增 ablation 显示 verifier 可以在 `turn on stove` 这类状态子任务上触发切换，但切到后续放置子任务后仍可能使原本成功的 baseline 失败；百炼 planner 真实路径复现了同样现象。下一步需要 fine-tuned verifier / 更稳的子任务完成判定 / executor-friendly subgoal policy，而不是简单把长程任务拆成 object-level `put` 子任务。

### 11. 2026-07-06 SAP recovery patch smoke

代码补丁：

- `ds.py`：移除 import-time `openai` 依赖；支持 `api_key_env`；规范化 OpenAI-compatible `base_url`，例如 `Codex.hldragon.xyz` 会变成 `https://Codex.hldragon.xyz/v1`；planner 调用固定 `temperature=0`；支持 `planner_style=outcome` 和论文式 `planner_style=paper_atomic`；`paper_atomic` 会把裸名词原子技能后处理成带冠词的 LIBERO/OpenVLA 风格短句。
- `main.py`：新增 primary/fallback planner 配置、`--llm_planner_style {outcome,paper_atomic}`、`--vlm_verifier_backend {qwen_local,openai_api,libero_oracle}`、`--vlm_history_length` 默认改为论文式 `2`、`--stuck_detection_mode {none,heuristic,vlm}`、`--recovery_max_attempts`、`--recovery_lift_steps`、`--recovery_lift_delta_z`、`--executor_instruction_mode`、`--verify_on_env_success`、`--vlm_completion_confirmations`；`executor_instruction_mode` 支持 `subtask`、`original`、`original_after_first_switch`、`subtask_with_original_context`、`subtask_with_progress_context`；成功时会把 env done 后的 terminal image 追加到 rollout video，避免视频最后一帧停在成功前。
- `qwenvl.py`：修正 `put/place ... in/on ...` 的 verifier prompt 位置短语；`pick up ... and place/put ... in/on ...` 会解析为最终 placement subgoal，不再误判为抓取-only；新增 `diagnose_stuck_with_qwen_vl()`；对 LIBERO `tomato sauce` / `alphabet soup` 加入物体外观 hint，对 basket/container 目标加入“进入篮筐内部/低于篮沿”的关系 hint。
- `api_vlm.py`：新增 OpenAI-compatible image verifier backend，复用双视角图像队列，支持 subgoal completion 和 stuck diagnosis；API VLM 调用固定 `temperature=0`，与本地 Qwen `do_sample=False` 对齐；同步加入 LIBERO 物体外观 / basket container hints；复合 pick-and-place 短句同样按最终 placement 验证。
- `oracle_verifier.py`：新增诊断-only LIBERO oracle verifier，直接读 simulator predicates，支持 `turnon/turnoff/open/close/in/on`、复合 pick-and-place 的最终 placement 谓词和近似 `pick up` 判断；用于分离视觉 verifier 误判与 executor 失败，不能作为论文 SAP 指标。
- `scripts/run_agentic_sap_smoke.sh`：不含密钥；默认读取 `OPENAI_API_KEY` / `OPENAI_BASE_URL`，默认 planner / API verifier model 为 `gpt-5.4-mini`，有 `DASHSCOPE_API_KEY` 时作为 planner fallback；`MANUAL_PLAN='step1||step2'` 可固定计划并绕开 planner；`LLM_PLANNER_STYLE=paper_atomic` 可切到论文式 atomic skill planner；API verifier 可用 `API_VLM_MODEL` / `API_VLM_BASE_URL` / `API_VLM_API_KEY_ENV` 单独切换到其他 OpenAI-compatible VLM；`SAVE_FRAMES=True` 可保存主视角 / eye-in-hand 诊断帧；设置 `VLM_VERIFIER_BACKEND=qwen_local` 可回到本地 Qwen verifier，设置 `VLM_VERIFIER_BACKEND=libero_oracle` 可跑 oracle 诊断。

验证结果：

```text
python -m py_compile experiments/robot/libero/main.py experiments/robot/libero/ds.py experiments/robot/libero/qwenvl.py experiments/robot/libero/api_vlm.py experiments/robot/libero/oracle_verifier.py
ar_agentic_libero: pass
ar_agentic_libero_vlm: pass

tools/smoke_libero_env.py: SMOKE_LIBERO_OK
planner-only OpenAI smoke:
- pre-existing host OPENAI_API_KEY/OPENAI_BASE_URL returned 401, plan=[]
- user-provided OpenAI-compatible endpoint Codex.hldragon.xyz + gpt-5.4-mini returned valid LIBERO-Long subtask plans
api-vlm smoke:
- user-provided endpoint accepted image inputs and returned Yes/No verifier responses
DashScope model probe:
- OpenAI-compatible `/models` returned vision IDs including `qwen3-vl-plus`, `qwen3-vl-flash`, `qwen-vl-plus`, `qwen-vl-max`
DashScope frame probe:
- `qwen3-vl-plus`: task2 early frame `No`, final burner frame `Yes`
- `qwen-vl-plus`: task2 early frame `No`, final burner frame `Yes`
container prompt probe:
- task0 saved final queue with object/container hint: tomato sauce early `No`, mid `No`, final `Yes`; alphabet soup final `Yes`
```

DashScope/Qwen-VL API verifier 可用同一 runner 切换，planner 仍可保持原 OpenAI-compatible endpoint：

```bash
export DASHSCOPE_API_KEY="..."
API_VLM_MODEL=qwen3-vl-plus \
API_VLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
API_VLM_API_KEY_ENV=DASHSCOPE_API_KEY \
VLM_VERIFIER_BACKEND=openai_api \
RUN_ID_NOTE=dashscope_qwen_vl_verifier_smoke \
bash scripts/run_agentic_sap_smoke.sh
```

新增 rollout / log：

| run_id_note | 目的 | 结果 |
|---|---|---|
| `post_sap_patch_openvla_smoke_1step` | 改动后默认 baseline 路径仍可执行 | OpenVLA 加载成功，1-step timeout，符合 smoke 预期 |
| `post_sap_patch_vlm_smoke_1step` | Qwen verifier 分支实际调用 | Qwen2.5-VL 加载成功，`[t=10]` verifier raw response `No`，1-step timeout |
| `post_sap_patch_recovery_forced_smoke` | 强制 heuristic stuck 覆盖 lift recovery 分支 | `[t=10]` verifier `No` 后执行 `Recovery action: lift gripper for 2 steps` |
| `openai_planner_sap_smoke_1step` | 组合入口：OpenAI-compatible planner + Qwen verifier + OpenVLA executor | planner 生成 `['put the alphabet soup in the basket', 'put the tomato sauce in the basket']`，verifier / executor 正常进入 1-step smoke |
| `api_vlm_planner_sap_smoke_1step` | 组合入口：OpenAI-compatible planner + API VLM verifier + OpenVLA executor | planner 生成同一两步 plan，API verifier 在 `[t=10]` 返回 `No`，1-step timeout 符合 smoke 预期 |
| `api_vlm_planner_sap_libero10_task2_ep0_1trial` | API VLM stuck diagnosis + recovery 的完整 episode | `turn on stove` 第一轮即误判 `Stuck`，过早 recovery 后失败 |
| `api_vlm_planner_sap_libero10_task2_ep0_no_recovery_1trial` | 关闭 recovery，隔离 API VLM completion gate | API verifier 在 `t=40` 将 `turn on stove` 判为完成并切到放置子任务；最终 `put moka pot on stove` timeout |
| `api_vlm_recovery_threshold_smoke_task2_ep0` | 验证 VLM stuck diagnosis 尊重 `--stuck_no_progress_checks` | 修复后 first `No` 不再触发 stuck diagnosis；第三次放置失败后才诊断 `Stuck` 并执行 recovery |
| `api_vlm_task2_original_after_first_switch_no_recovery_1trial` | 切到第二 subtask 后恢复原始完整 executor 指令 | 仍 timeout，说明只在切换后恢复原始指令不够 |
| `api_vlm_task2_original_executor_no_recovery_1trial` | executor 始终使用原始完整任务，verifier 仍按两步 plan 检查 | env success `1/1`，`t=294` 成功；但 verifier 未确认第二 subtask |
| `api_vlm_task2_original_executor_freq10_loose_place_1trial` | 放宽 placement prompt | env success，但 verifier 在 `t=60` 对仍在桌上的 moka pot 假阳性，不能采用 |
| `api_vlm_task2_original_executor_confirm2_final_check_1trial` | 严格 stove target hint + 两次确认 + env-success 终态检查 | env success `1/1`；两次确认抑制单次假阳性，但 final API VLM 仍判 placement `Not Complete` |
| `api_vlm_task0_ep1_original_executor_confirm2_final_frame_1trial` | 多物体 basket：原始 executor 指令 + 两步 verifier plan + terminal frame | env success `1/1`；API VLM 对第一步 basket subgoal 只有一次 pending positive，final check 仍 `Not Complete` |
| `dashscope_qwen3vl_task2_original_executor_confirm2_final_check_1trial` | DashScope `qwen-plus` planner + `qwen3-vl-plus` verifier；executor 保持原始完整任务 | env success `1/1`；final VLM check 对 `put the moka pot on the stove` 判 Complete |
| `dashscope_qwen3vl_task2_subtask_no_recovery_1trial` | 更接近 SAP 的 subtask executor，无 recovery | `turn on stove` 在 `t=140` 切换；`put moka pot on stove` 到 `t=340` timeout，失败 |
| `dashscope_qwen3vl_task2_subtask_heuristic_recovery_1trial` | subtask executor + heuristic stuck + lift recovery | `turn on stove` 在 `t=130` 切换；第二子任务触发两次 recovery 后仍失败，`t=360` recovery limit exceeded |
| `dashscope_qwen3vl_task2_original_after_first_switch_1trial` | 第一子任务用 subtask，切换后 executor 恢复完整原始任务 | env success `1/1`；final VLM check 仍判第二子任务 `Not Complete` |
| `dashscope_qwen3vl_task2_subtask_with_context_1trial` | executor 指令为原始任务 + 当前子任务上下文 | 仍 timeout；简单拼接上下文不能修复孤立子任务执行 |
| `dashscope_qwen3vl_task2_original_after_first_switch_hist5_1trial` | `original_after_first_switch` + `vlm_history_length=5` | `t=240` 第二子任务 VLM Complete，`t=255` env success；当前 task2 上最接近 PEV 闭环的非官方配置 |
| `dashscope_qwen3vl_task2_subtask_hist5_1trial` | 纯 subtask executor + `vlm_history_length=5` | `turn on stove` 在 `t=110` 切换；第二子任务仍到 `t=340` timeout |
| `dashscope_qwen3vl_task0_ep1_original_after_first_switch_hist5_1trial` | task0 episode1，多物体 basket，best-current task2 配置 | 一直未确认 `put alphabet soup in basket`，first-subtask executor 到 `t=370` timeout |
| `dashscope_qwen3vl_task0_ep1_original_executor_hist5_1trial` | task0 episode1，executor 始终保持完整原始任务 | env success `1/1`，但 first subgoal 和 final VLM check 均 `Not Complete` |
| `dashscope_qwen3vl_task0_ep1_original_executor_hist5_saveframes_1trial` | 同上，开启 `SAVE_FRAMES=True` 采集主视角/手眼诊断帧 | env success；该轨迹中 alphabet soup 在 `t=130` 判 Complete，tomato sauce 仍漏判 |
| `dashscope_qwen3vl_task0_ep1_original_executor_hist5_containerhint_1trial` | 加入 LIBERO object/container hints 后复跑 task0 episode1 | `t=130` alphabet soup Complete，`t=240` tomato sauce Complete，`t=272` env success |
| `dashscope_qwen3vl_task2_paper_atomic_subtask_hist5_1trial` | 论文式 `paper_atomic` planner + 真实 subtask executor | `turn on` 和 `pick up` 均完成切换；`place moka pot on stove` 到 `t=370` timeout |
| `dashscope_qwen3vl_task2_paper_atomic_original_after_first_switch_hist5_1trial` | `paper_atomic` planner + 切换后恢复原始完整 executor 指令 | `t=50` turn on Complete，`t=230` pick up Complete，`t=240` place Complete，`t=255` env success |
| `oracle_task2_paper_atomic_subtask_1trial` | `paper_atomic` planner + oracle verifier 诊断 | planner endpoint 返回 401，fallback 到原始任务，run 已中止/不可作为 SAP 结果 |
| `oracle_task2_manual_atomic_subtask_1trial` | 手工无冠词原子 plan + oracle verifier + subtask executor | oracle unwrap 修复前一直未解析到 predicate，失败；该 run 只用于暴露 wrapper bug |
| `oracle_task2_manual_atomic_subtask_unwrapfix_1trial` | 修复 oracle unwrap 后，无冠词 `turn on stove` + subtask executor | 520 steps 内真实 `Turnon` 未完成，说明 OpenVLA 对 bare noun subtask wording 敏感 |
| `oracle_task2_turnon_article_subtask_1trial` | 只测 `turn on the stove` 一步 + oracle verifier | `t=110` oracle 判 `Turnon flat_stove_1` Complete，证明带冠词 wording 可执行 |
| `oracle_task2_manual_atomic_articles_subtask_1trial` | 带冠词三步 atomic plan + oracle verifier + 真实 subtask executor | `t=110` turn on Complete，`t=180` pick up Complete；`place the moka pot on the stove` 到 `t=530` timeout |
| `oracle_task2_manual_atomic_articles_original_after_first_switch_1trial` | 带冠词三步 atomic plan + oracle verifier + 切换后恢复原始完整 executor 指令 | `t=110` turn on Complete，`t=160` pick up Complete，`t=289` env success；final oracle check 对 place 判 Complete |
| `oracle_task2_manual_atomic_articles_put_subtask_1trial` | 三步 atomic plan，把最后一步从 `place` 换成 `put` | 前两步完成；`put the moka pot on the stove` 仍到 `t=530` timeout，说明不是 `place` 动词单点问题 |
| `oracle_task2_two_step_articles_subtask_1trial` | 两步 outcome plan + 纯 `subtask` executor | `t=110` turn on Complete；`put the moka pot on the stove` 仍到 `t=530` timeout |
| `oracle_task2_two_step_articles_progress_context_1trial` | 两步 outcome plan + `subtask_with_progress_context` executor | `t=110` turn on Complete，`t=257` env success；final oracle check 对第二步判 Complete |
| `api_vlm_task2_two_step_progress_context_short` | 尝试用当前 shell 的 OpenAI-compatible env 验证 API VLM progress-context | API VLM 请求返回 401 invalid token，run 已中止；不能作为 verifier 结果 |
| `qwen_local_task2_two_step_progress_context_hist5_1trial` | 本地 Qwen2.5-VL verifier + 两步 progress-context executor | `t=110` Qwen 确认 turn on，`t=190` Qwen 确认 placement/plan finished，`t=290` env success |
| `dashscope_qwen3vl_task2_two_step_progress_context_hist5_1trial` | DashScope `qwen3-vl-plus` API verifier + 两步 progress-context executor | `t=110` 确认 turn on，`t=250` 确认 moka pot placement/plan finished，`t=263` env success |
| `dashscope_planner_qwen3vl_task2_progress_context_hist5_1trial` | `qwen-plus` planner + `qwen3-vl-plus` API verifier + progress-context executor，无 manual plan | planner 生成两步 outcome plan；`t=110` 确认 turn on，`t=240` 确认 moka pot placement/plan finished，`t=262` env success |
| `qwen_local_task0_ep1_two_step_progress_context_hist5_1trial` | 本地 Qwen2.5-VL verifier + task0 basket 两步 progress-context | 一直未确认 `put alphabet soup in basket`，`t=530` timeout |
| `oracle_task0_ep1_two_step_progress_context_1trial` | oracle verifier + task0 basket 两步 progress-context | oracle 同样未确认第一步，`t=530` timeout；定位为 executor/subgoal policy 未完成，而不是 Qwen 视觉漏判 |
| `oracle_task0_ep1_pickplace_progress_context_1trial` | oracle verifier + LIBERO-object 风格 `pick up ... and place ...` 子目标 | verifier parser 按最终 basket placement 验收；第一步仍未完成，`t=530` timeout |
| `oracle_task0_ep1_two_step_original_context_1trial` | oracle verifier + `subtask_with_original_context` | 第一子任务仍未完成，`t=530` timeout；原始任务上下文没有修复 task0 |
| `oracle_task0_ep1_swap_order_progress_context_1trial` | oracle verifier + task0 basket 两步 progress-context，交换物体顺序 | 第一子任务 `put the tomato sauce in the basket` 仍到 `t=530` timeout；说明不是 alphabet-soup-first 单点问题 |
| `oracle_task0_ep1_original_executor_two_step_1trial` | executor 始终用原始完整任务，oracle verifier 仍按两步 basket subgoal 检查 | `t=150` alphabet soup Complete；`t=272` env success，terminal final oracle check 判 tomato sauce Complete；oracle/parser sanity check 通过 |
| `oracle_task3_ep1_two_step_progress_context_1trial` | task3 drawer 任务 + progress-context + oracle | `t=170` bowl-in-bottom-drawer Complete；随后 close drawer 到 `t=430` timeout |
| `oracle_task3_ep1_original_executor_two_step_520_1trial` | task3 drawer 任务 + original executor + oracle，520-step cap | `t=150` bowl-in-bottom-drawer Complete；close drawer 到 `t=530` timeout |
| `openvla_task3_ep1_baseline_control_1trial` | task3 episode1 纯 OpenVLA baseline control | 同 task/episode 在当前单跑控制下 `t=530` timeout；task3 不能作为稳定正例 |
| `oracle_task5_ep0_pick_place_progress_context_1trial` | task5 book/caddy，两步 pick/place + progress-context + oracle | `t=70` pick up Complete；`t=200` env success，terminal final oracle check 对 caddy placement 判 Complete |
| `qwen_local_task5_ep0_pick_place_progress_context_hist5_1trial` | task5 book/caddy，两步 pick/place + local Qwen | Qwen 对 `pick up the book` 始终 `No`，`t=430` timeout |
| `qwen_local_task5_ep0_pick_place_progress_context_relaxed_pick_hist5_1trial` | 同上，但放宽 pick-up prompt 对遮挡的描述 | 仍始终 `No`，`t=430` timeout |
| `qwen_local_task5_ep0_composite_progress_context_hist5_1trial` | task5 单一 composite subtask，local Qwen 只验最终 placement | executor env success `t=174`；final Qwen check 仍 `Not Complete`，说明 caddy placement 视觉 gate 也不稳定 |
| `dashscope_qwen3vl_task5_ep0_pick_place_progress_context_hist5_1trial` | task5 book/caddy，两步 progress-context + DashScope API VLM，history=5 | `t=70` pick-up Complete；env success `t=200`，但 final caddy placement 仍 `Not Complete` |
| `dashscope_qwen3vl_task5_ep0_pick_place_progress_context_caddyhint_hist5_1trial` | 补 caddy/black-book hint 后复跑，history=5 | 仍 `t=70` pick-up Complete；env success `t=200`，final caddy placement 仍 `Not Complete` |
| `dashscope_qwen3vl_task5_ep0_pick_place_progress_context_caddyhint_hist1_1trial` | 同上，改为 `vlm_history_length=1` | `t=70` pick-up Complete，`t=110` caddy placement Complete/plan finished，`t=217` env success |
| `dashscope_planner_qwen3vl_task5_progress_context_hist1_1trial` | `qwen-plus` planner + `qwen3-vl-plus` API verifier + progress-context executor，无 manual plan | planner 保留单一 outcome-level transfer；`t=100` verifier 确认完成/plan finished，`t=172` env success |

关键日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_06-18_16_55--post_sap_patch_openvla_smoke_1step.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_06-18_18_46--post_sap_patch_vlm_smoke_1step.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_06-18_25_15--post_sap_patch_recovery_forced_smoke.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-18_40_07--openai_planner_sap_smoke_1step.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-19_02_30--api_vlm_planner_sap_smoke_1step.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-19_03_39--api_vlm_planner_sap_libero10_task2_ep0_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-19_06_30--api_vlm_planner_sap_libero10_task2_ep0_no_recovery_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-19_15_51--api_vlm_recovery_threshold_smoke_task2_ep0.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-19_35_40--api_vlm_task2_original_after_first_switch_no_recovery_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-19_42_09--api_vlm_task2_original_executor_no_recovery_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-19_55_04--api_vlm_task2_original_executor_freq10_loose_place_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-20_25_59--api_vlm_task2_original_executor_confirm2_final_check_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_06-20_48_31--api_vlm_task0_ep1_original_executor_confirm2_final_frame_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-05_17_01--dashscope_qwen3vl_task2_original_executor_confirm2_final_check_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-05_21_35--dashscope_qwen3vl_task2_subtask_no_recovery_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-05_27_31--dashscope_qwen3vl_task2_subtask_heuristic_recovery_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-05_44_09--dashscope_qwen3vl_task2_original_after_first_switch_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-06_04_17--dashscope_qwen3vl_task2_subtask_with_context_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-06_12_36--dashscope_qwen3vl_task2_original_after_first_switch_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-06_16_47--dashscope_qwen3vl_task2_subtask_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-06_27_55--dashscope_qwen3vl_task0_ep1_original_after_first_switch_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-06_33_23--dashscope_qwen3vl_task0_ep1_original_executor_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-06_43_43--dashscope_qwen3vl_task0_ep1_original_executor_hist5_saveframes_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-06_57_28--dashscope_qwen3vl_task0_ep1_original_executor_hist5_containerhint_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-07_22_36--dashscope_qwen3vl_task2_paper_atomic_subtask_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-07_27_43--dashscope_qwen3vl_task2_paper_atomic_original_after_first_switch_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-07_46_36--oracle_task2_paper_atomic_subtask_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-07_48_56--oracle_task2_manual_atomic_subtask_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-07_59_27--oracle_task2_manual_atomic_subtask_unwrapfix_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-08_03_49--oracle_task2_turnon_article_subtask_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-08_06_39--oracle_task2_manual_atomic_articles_subtask_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-08_17_13--oracle_task2_manual_atomic_articles_original_after_first_switch_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-08_40_13--oracle_task2_manual_atomic_articles_put_subtask_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-08_46_47--oracle_task2_two_step_articles_subtask_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-08_51_36--oracle_task2_two_step_articles_progress_context_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-08_54_44--api_vlm_task2_two_step_progress_context_short.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-09_10_34--qwen_local_task2_two_step_progress_context_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-11_29_11--dashscope_qwen3vl_task2_two_step_progress_context_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-11_45_49--dashscope_planner_qwen3vl_task2_progress_context_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-09_18_22--qwen_local_task0_ep1_two_step_progress_context_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-09_26_31--oracle_task0_ep1_two_step_progress_context_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-09_40_49--oracle_task0_ep1_pickplace_progress_context_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-09_46_15--oracle_task0_ep1_two_step_original_context_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-10_00_16--oracle_task0_ep1_swap_order_progress_context_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-10_10_41--oracle_task0_ep1_original_executor_two_step_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-10_27_21--oracle_task3_ep1_two_step_progress_context_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-10_32_22--oracle_task3_ep1_original_executor_two_step_520_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-10_37_42--openvla_task3_ep1_baseline_control_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-10_50_06--oracle_task5_ep0_pick_place_progress_context_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-10_57_54--qwen_local_task5_ep0_pick_place_progress_context_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-11_01_16--qwen_local_task5_ep0_pick_place_progress_context_relaxed_pick_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-11_05_44--qwen_local_task5_ep0_composite_progress_context_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-11_13_36--dashscope_qwen3vl_task5_ep0_pick_place_progress_context_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-11_19_23--dashscope_qwen3vl_task5_ep0_pick_place_progress_context_caddyhint_hist5_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-11_23_29--dashscope_qwen3vl_task5_ep0_pick_place_progress_context_caddyhint_hist1_1trial.txt
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_07-11_51_55--dashscope_planner_qwen3vl_task5_progress_context_hist1_1trial.txt
```

注意：`ar_agentic_libero_vlm` 仍会提示 `transformers==4.51.3` 与 OpenVLA 推荐 `4.40.1` 不一致；该环境只用于 verifier / SAP smoke，完整 executor baseline 仍应使用 `ar_agentic_libero`。

## 完整评估命令

已用以下形式跑通 `libero_spatial`、`libero_object`、`libero_goal` 和 `libero_10`。要复跑或切 suite，只需替换 checkpoint 和 `--task_suite_name`：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
    --task_suite_name libero_spatial \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --local_log_dir "$REPRO_ROOT/data/logs"
```

要跑论文级指标，建议按官方默认 suite 分别跑：

- `libero_spatial`: `openvla/openvla-7b-finetuned-libero-spatial`
- `libero_object`: `openvla/openvla-7b-finetuned-libero-object`
- `libero_goal`: `openvla/openvla-7b-finetuned-libero-goal`
- `libero_10`: `openvla/openvla-7b-finetuned-libero-10`

## 对官方代码的必要修正

已在本地 `repos/agentic-robot/experiments/robot/libero/main.py` 做了最小 patch，并保存到：

```text
patches/agentic_robot_main_smoke.patch
```

修正内容：

1. `qwenvl.py` 依赖 `Qwen2_5_VLForConditionalGeneration`，但 OpenVLA 推荐的 `transformers==4.40.1` 不支持该类。已改为延迟到 `load_qwen_vl_model()` 内部导入，使当前 OpenVLA executor 环境可以正常 import；真正启用 VLM verifier 时仍需要更新版 `transformers`。
2. 增加 `--start_task_id`、`--max_tasks`、`--start_episode_id`、`--max_steps_override`，用于最小 smoke eval 和指定初始状态 ablation。默认值不改变完整评估行为。
3. 增加显式 SAP 控制参数：`--enable_vlm_verifier`、`--use_llm_planner`、`--manual_plan`、`--llm_planner_api_key_env`、`--llm_planner_fallback_api_key_env`、`--vlm_verifier_backend`、`--api_vlm_model`、`--vlm_model_id`、`--vlm_attn_implementation`、`--vlm_history_length`、`--executor_instruction_mode`、`--verify_on_env_success`、`--vlm_completion_confirmations` 等。`vlm_verifier_backend=libero_oracle` 只用于诊断；`executor_instruction_mode=subtask_with_progress_context` 只改变 executor prompt，不改变 verifier 的当前子任务判定；默认不启用 planner / verifier，因此已完成的 baseline 仍是纯 OpenVLA executor。
4. 当 multi-step plan 存在但 VLM verifier 未启用时，本地代码会回退到原始任务指令，避免只执行第一个 subtask 后无法推进。
5. `ds.py` planner prompt 改为 executor-friendly outcome-level planning：单对象 transfer 保留原始 wording，多对象任务按对象 outcome 拆分；避免早期 atomic `pick/place` prompt 导致 executor 退化。论文式 `paper_atomic` 路径保留为显式 ablation，并对裸名词原子技能补默认冠词以匹配 OpenVLA 的自然语言分布。
6. 补齐论文式二级 verification/recovery 控制面：verifier 返回 `No` 后可用 heuristic 或 VLM 做 stuck diagnosis，触发 lift-gripper recovery，并受 `--recovery_max_attempts` 限制。VLM stuck diagnosis 现在同样尊重 `--stuck_no_progress_checks`，避免 first `No` 直接触发 recovery。

## 关键依赖坑

1. 官方 Agentic Robot repo 不是 standalone，缺少 `prismatic` 源码。这里额外 clone 并 editable 安装了 `moojink/openvla-oft`。
2. LIBERO 当前 checkout 的 `setup.py` 没有正确暴露 `libero.libero`，运行时必须设置：

```bash
PYTHONPATH="$REPRO_ROOT/repos/LIBERO"
LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config"
```

3. `robosuite==1.4.1` 与新 `mujoco==3.10.0` API 不兼容，已固定为：

```text
mujoco==2.3.7
```

4. headless 渲染需要系统 GL 库，已安装：

```bash
apt-get install -y libosmesa6 libegl1 libopengl0 libgl1
```

5. TensorFlow 2.15 / TFDS 4.9.3 组合需要较旧 metadata/protobuf 组合：

```text
tensorflow-metadata==1.14.0
protobuf==3.20.3
wandb==0.16.6
```

6. 官方模型加载硬编码 `flash_attention_2`，已安装：

```text
flash-attn==2.5.5
```

## 重要代码审计发现

原始开源版 `main.py` 不能完整代表论文里的 SAP + VLM verifier 闭环：

1. 代码中明确设置了 `VLM_ENABLED_EFFECTIVELY = False`，并打印 `No VLM`。
2. 虽然有 `hardcoded_plan`，但实际执行时设置的是：

```python
current_subtask_instruction = original_task_description
```

也就是说，原始默认 eval 更接近 OpenVLA executor 评估，而不是论文完整的 Planner-Executor-Verifier 闭环。本地 patch 已把 planner / verifier 做成显式可开关路径，且 verifier 集成 smoke 已通过；DashScope `qwen-plus` planner 路径也已验证。完整 SAP 指标仍未完成，剩余条件是：

- 当前 zero-shot Qwen verifier 没有稳定复现论文 LoRA fine-tuned verifier 的 subgoal completion gate；论文消融也显示 zero-shot verifier 会显著下降。
- `libero_10` task 0 episode 1 上，object-level split 从原始完整任务的 `1/1` 退化为 `0/1`，说明简单拆成 `put object in basket` 不能代表论文 SAP。
- `libero_10` task 2 episode 0 上，本地 Qwen verifier 与 API VLM verifier 都能把 `turn on stove` 判为完成并切换，但后续 `put moka pot on stove` timeout；同一初始状态原始完整任务 baseline 成功。
- `libero_10` task 2 episode 0 上，`--executor_instruction_mode original` 可以在 planner/verifier 仍按两步运行时恢复 env success；这说明 OpenVLA 对孤立 subgoal 的 executor conditioning 是主要退化点之一，但这不是论文报告的完整 SAP 设置。
- `subtask_with_progress_context` 在同一 task2/episode0 上比 `original_after_first_switch` 更少泄漏完整原始指令：verifier 仍按当前 subtask 判断，executor 只得到原始任务、已完成步骤和当前步骤。oracle 诊断中该模式用两步 plan 在 `t=257` 完成 env success + final oracle completion，是当前最强的开源 SAP-style executor evidence；仍需用真实 VLM verifier 和更多 tasks 验证。
- DashScope `qwen3-vl-plus` 能在 task2 终态把 `moka pot on stove` 判 Complete，优于此前通用 API VLM 的终态漏判；`--vlm_history_length 5` 还能让 `original_after_first_switch` 在 task2 上完成 VLM plan confirmation + env success。但在真实 `--executor_instruction_mode subtask` 下，即使用 history=5、无 recovery / heuristic recovery 仍失败，说明 verifier 改善不足以复现论文完整闭环。
- `--llm_planner_style paper_atomic` 已可生成论文式原子技能序列，并会把裸名词技能规范成带冠词短句。oracle 诊断显示 `turn on stove` 不触发真实 `Turnon`，而 `turn on the stove` 在 `t=110` 可完成；但即使用带冠词三步 atomic plan，真实 subtask executor 仍卡在最后 `place the moka pot on the stove`，需要完整任务上下文才恢复成功。
- `subtask_with_original_context` 这种简单 prompt 拼接仍失败，说明 OpenVLA 的 long-horizon executor conditioning 不能只靠在子任务指令后附加原始目标修复。
- `libero_10` task 0 episode 1 上，加入 LIBERO object/container hints 后，`qwen3-vl-plus` + history=5 可以在 original executor context 下完成两个 basket 子目标的 VLM confirmation；但 first-subtask executor 仍失败，说明多物体任务依然需要 executor-friendly subgoal policy 或论文式训练/闭环。
- `libero_oracle` verifier 已验证可用于排除视觉漏判：在 `original_after_first_switch` 成功轨迹上，final oracle check 对 `place the moka pot on the stove` 判 `Complete`；但它读取 simulator predicates，只能作为诊断上界，不能作为论文 SAP 指标。
- API VLM stuck diagnosis 可运行，但直接用通用模型会过早/过严地诊断 `Stuck`；已修复 first `No` 立即 recovery 的控制流问题，但它仍不能替代论文 fine-tuned verifier。
- API VLM placement verifier 存在两类错误：宽松 prompt 会早期假阳性，严格 stove target prompt 在 env success 终态仍可能判 `Not Complete`。两次确认可抑制单次假阳性，但不能解决终态漏判。
- 系统预置的 `OPENAI_API_KEY` / `OPENAI_BASE_URL` planner-only smoke 返回 401；用户提供的 OpenAI-compatible endpoint 已用 `gpt-5.4-mini` 验证可用。未把明文 key 写入文件；复跑时应只通过 shell 环境变量传入 `OPENAI_API_KEY`，必要时设置 `DASHSCOPE_API_KEY` 作为 fallback。
- 若继续追求论文完整设置，需要确认 / 复现 fine-tuned verifier、recovery 逻辑、verifier 频率、历史帧长度和 executor-friendly subgoal policy。
- 当前 atomic `pick/place` 分解在 `libero_spatial` task 0 上使 executor 从对照 `1/1` 变成 `0/1`，因此不能直接用朴素分解代表论文 SAP。

## 参考源

- Agentic Robot: https://github.com/Agentic-Robot/agentic-robot
- Paper: https://arxiv.org/abs/2505.23450
- Project page: https://agentic-robot.github.io/
- OpenVLA-OFT: https://github.com/moojink/openvla-oft
- LIBERO setup notes: https://github.com/moojink/openvla-oft/blob/main/LIBERO.md
