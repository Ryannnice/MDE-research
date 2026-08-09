# PIPER D455 RGB-D/IMU 诊断

这个目录在 Windows 上同时验证 D455 的 RGB、深度和 IMU，并保存一组可复查的结果。它不会控制机械臂。

当前 D455 已机械固定在机械臂末端附近，画面下缘能看到夹爪，因此按腕部相机（eye-in-hand）使用。相机的数据线仍直接连接 Windows USB 3.x；PIPER 末端两针接口不是 USB。

当前固定配置：

- D455 序列号 `260722303168`
- RGB：848×480 @ 30 Hz
- 深度：848×480 @ 30 Hz，随后对齐到 RGB
- 加速度计：200 Hz
- 陀螺仪：200 Hz
- RealSense SDK/Python：2.58.1.10581

不要同时打开 RealSense Viewer 和诊断脚本，否则两个程序可能争用相机。

## Windows 环境

当前现场电脑已经创建：

```text
C:\Desktop\PIPER\camera\.venv
```

重建环境时使用：

```powershell
C:\Users\renyv\AppData\Local\Programs\Python\Python312\python.exe `
    -m venv C:\Desktop\PIPER\camera\.venv

C:\Desktop\PIPER\camera\.venv\Scripts\python.exe `
    -m pip install -r C:\Desktop\PIPER\camera\requirements-windows.txt
```

## 采集

```powershell
cd C:\Desktop\PIPER\camera
.\.venv\Scripts\python.exe .\realsense_diagnostic.py `
    --output .\captures\latest
```

近距离 A/B 测试可以临时使用高密度预设和视差偏移；程序退出时会恢复相机的完整原始设置：

```powershell
.\.venv\Scripts\python.exe .\realsense_diagnostic.py `
    --visual-preset high-density `
    --disparity-shift 50 `
    --output .\captures\near50
```

输出：

- `color.png`：RGB 图像；
- `aligned_depth_raw.png`：对齐到 RGB 的 16 位原始深度；
- `depth_preview.png`：便于查看的伪彩深度；
- `combined_preview.png`：RGB 与深度并排图；
- `metadata.json`：设备、内参、外参、帧率、时间戳、IMU 和深度质量。

## D455 + PIPER-X 统一时间戳快照

手眼标定完成后，可在 observe 桥运行时采集一组 RGB、对齐深度、IMU、关节、法兰、夹爪与 Base 坐标点云：

```powershell
cd C:\Desktop\PIPER\camera
.\.venv\Scripts\python.exe .\synchronized_snapshot.py `
    --output .\captures\synchronized_latest
```

工具没有运动接口。它使用 D455 `global_time` 曝光时间，同时在后台以 100 Hz 读取本机观察桥，并从环形缓冲中选取最接近曝光时刻的法兰反馈。只有以下条件全部满足才保存：

- 桥为 `observe`，机械臂型号为 `piper_x`；
- RGB 与深度时间差不超过 5 ms；
- 法兰反馈与相机曝光时间差不超过 8 ms；
- 被选中的桥请求往返时间不超过 10 ms；
- Base 点云有效点不少于 10,000。

输出：

- `snapshot.json`：统一时间、机器人/夹爪状态、相机内参、三段坐标矩阵和验收项；
- `color.png`、`aligned_depth_raw.png`、`depth_preview.png`；
- `base_point_cloud.ply`：带 RGB 的二进制 PLY，坐标单位为米，坐标系为 PIPER Base。

2026-08-09 静态实测：RGB/深度时间差 `0.035 ms`，法兰/曝光时间差 `5.420 ms`，桥往返 `4.094 ms`，生成 `308,677` 个 Base 点；所有验收项通过。正式摘要保存在 `results/synchronized_snapshot_final.json`。点云中约 `90.6%` 的点位于已知桌面高度 ±3 cm 内，进一步核验了 Base 坐标方向与尺度。

这一步验证的是静态/慢速快照。后续连续运动数据集应沿用同一时间基准做多帧记录，并对相邻法兰位姿插值，不能把单帧快照工具直接宣称为高速硬件同步。

## 2026-08-02 实机结果

同一静止姿态下完成了四组 848×480@30 Hz 采样：

| 配置 | 有效深度像素 | 深度 5–95% 分位 | 用途 |
|---|---:|---:|---|
| 原始 Custom | 24.33% | 约 0.330–0.783 m | 保留远处深度 |
| High Density | 22.40% | 约 0.331–0.640 m | 本场景无收益 |
| High Density + shift 50 | 28.51% | 约 0.241–0.467 m | 腕部中近距折中 |
| High Density + shift 100 | 40.78% | 约 0.190–0.395 m | 最后近抓取阶段 |

结论：D455 的物理基线决定了默认近距深度比较稀疏。`shift 100` 能明显增加当前腕部视角的近距覆盖，但会截断 0.41 m 之外的深度；不能把它当成全场景配置。建议保留两种运行档：接近目标前使用原始配置或 `shift 50`，最后近抓取阶段才使用 `shift 100`。RGB 在所有配置下都正常。

注意：写入 disparity shift 后，SDK 会把当前 preset 名称显示为 `Custom (0)`；这是高级参数被修改后的正常表现，不表示 High Density 基础参数没有应用。

参数只在单次诊断进程内临时生效，退出后恢复为现场原值：Custom、发射器开启、激光功率 150、disparity shift 0。
