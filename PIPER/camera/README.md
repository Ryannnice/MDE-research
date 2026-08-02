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
