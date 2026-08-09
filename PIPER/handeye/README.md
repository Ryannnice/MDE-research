# PIPER D455 眼在手上标定

当前结构是 D455 随 PIPER 法兰运动、ChArUco 板固定在桌面，即 eye-in-hand。工具只从观察桥读取法兰位姿并采集相机，不包含机械臂运动命令。

当前实机经控制器末端反馈与候选机型 FK 交叉核验为 `piper_x`。采样程序会拒绝其他机型配置，并要求控制器法兰反馈与关节 FK 的差异不超过 2 mm / 0.5°，防止错误机型污染数据集。

## 坐标约定

- `base_from_flange`：PIPER SDK 的法兰位姿，点从法兰坐标系变换到基座坐标系。
- `target_to_camera`：ChArUco 板坐标系到 D455 彩色相机坐标系。
- 求解结果 `camera_to_flange`：点从相机坐标系变换到法兰坐标系，即 OpenCV 的 `cam2gripper`。
- PIPER RPY 使用 `Rz(yaw) @ Ry(pitch) @ Rx(roll)`，与 pyAgxArm 源码一致。

D455 彩色流当前报告 Inverse Brown-Conrady。程序不把这组系数直接交给 OpenCV，而是使用 RealSense `rs2_deproject_pixel_to_point(..., depth=1)` 把每个 ChArUco 角点转换成归一化光线，再调用 `solvePnP`。

## 当前实机结果（2026-08-09）

本结果只适用于当前 PIPER-X、D455 彩色光学坐标系（序列号 `260722303168`）和当前相机支架位置。15 个校准样本、3 个独立留出样本，最终选择 Park：

- 校准残差：`4.606 mm / 0.788°` RMS；
- 留出验证：`3.660 mm / 0.663°` RMS，最大 `4.380 mm / 0.843°`；
- 姿态覆盖：平移 `355 mm`、旋转 `71.9°`，双旋转轴比 `0.514`；
- 最终文件：`results/handeye_final_park.json`；
- 验证文件：`results/validation_final_park.json`；
- 对齐深度全链路实测：24/24 角点，板面刚体拟合 `0.692 mm` RMS；
- 深度点经相机、法兰换算到基座后，固定标定板位姿与标定参考相差 `3.469 mm / 0.513°`；
- 深度链报告：`results/depth_chain_verification.json`。

最终 `camera_to_flange`（即点从 D455 彩色相机坐标系变换到法兰坐标系的 `flange_T_camera`）为：

```text
 0.999848941743  -0.015307936375   0.008231693617   0.011914031905
 0.011393842768   0.934920176876   0.354675123481  -0.098166262458
-0.013125320676  -0.354527756253   0.934953365684   0.046392155899
 0.000000000000   0.000000000000   0.000000000000   1.000000000000
```

平移为 `[11.914, -98.166, 46.392] mm`，ZYX RPY 为 `[-20.766°, 0.752°, 0.653°]`。把彩色相机点变换到机器人基座时使用：

```text
base_p = base_T_flange @ flange_T_camera @ camera_p
```

若三维点来自“对齐到彩色相机”的深度图，可直接使用本外参；若使用原始深度光学坐标系，必须先应用 D455 的 `color_T_depth`。相机或支架只要发生松动、拆装或转动，就必须重新标定。

开始前可随时运行只读预检；它同时核验桥、PIPER-X 机型、控制器/FK 位姿一致性和指定 D455：

```powershell
C:\Desktop\PIPER\camera\.venv\Scripts\python.exe .\handeye_calibration.py preflight
```

## 1. 标定板

```powershell
cd C:\Desktop\PIPER\handeye
C:\Desktop\PIPER\camera\.venv\Scripts\python.exe .\handeye_calibration.py board
```

打印 `board\piper_charuco_7x5_a4_landscape.pdf`：

- A4 横向；
- 100% 原始尺寸；
- 关闭“适应页面、缩小超大页面”等自动缩放；
- 打印后量出标尺必须为 100 mm，单格必须为 30 mm；
- 平整粘贴到刚性平板，并固定在桌面；整个数据集期间不能移动。

## 2. 采集单个姿态

在拖动示教模式下手动把相机移到能看到标定板的位置，双手离开机械臂并完全停稳后运行：

```powershell
C:\Desktop\PIPER\camera\.venv\Scripts\python.exe .\handeye_calibration.py capture
```

程序要求：至少 12 个 ChArUco 角点、PnP 近似残差不超过 1.5 px、相机角速度不超过 0.05 rad/s、关节漂移不超过 0.1°，并拒绝近乎重复的法兰姿态。成功样本写入 `dataset\sample_NNN`。

建议采集 15–25 个姿态：位置和距离都要变化，尤其要围绕至少两个不同旋转轴改变相机朝向；标定板必须始终固定。

## 3. 求解

```powershell
C:\Desktop\PIPER\camera\.venv\Scripts\python.exe .\handeye_calibration.py solve
```

程序同时运行 Tsai、Park、Horaud、Andreff、Daniilidis 五种 OpenCV 方法，并用“标定板在基座中的估计是否保持不变”计算平移/旋转残差。结果保存在 `results\handeye_result.json`。

在接受结果前至少检查：

- 样本不少于 15；
- 旋转跨度大于 20°且覆盖两个独立旋转轴；
- 多种算法结果相互接近；
- 留出姿态下标定板基座位姿仍稳定。

## 4. 独立留出验证

校准样本完成后，另外采集至少 3 个不参与求解的姿态：

```powershell
C:\Desktop\PIPER\camera\.venv\Scripts\python.exe .\handeye_calibration.py capture --dataset validation_dataset
C:\Desktop\PIPER\camera\.venv\Scripts\python.exe .\handeye_calibration.py validate
```

`validate` 使用已求得的 `camera_to_flange`，逐姿态重新计算固定标定板的基座位姿，并输出平移/旋转 RMS、最大值和每个样本的残差。不要把留出样本重新混入校准集后再报告同一组验证指标。

## 5. 对齐深度到机器人基座的实物复核

让标定板继续固定，D455 距板约 45–60 cm、完整看到标定板并完全静止，然后运行：

```powershell
C:\Desktop\PIPER\camera\.venv\Scripts\python.exe .\depth_chain_verification.py
```

工具只读取 observe 桥。它把对齐到彩色相机的深度角点依次通过：

```text
base_p = base_T_flange @ flange_T_camera @ camera_p
```

并检查板面刚体拟合、30 mm 相邻角点边长、RGB PnP 与深度的一致性，以及固定标定板在机器人基座中的位姿。正式实测 24 个角点全部通过，结果写入 `results\depth_chain_verification.json`，标定文件 SHA-256 为 `364e578e1ce82d547e990c1bed39d66ecb869b7e741b45779576384c79e308d6`。

D455 离板约 18 cm 时，RGB 虽能识别全部角点，但板面深度几乎全为空洞；这不是手眼矩阵错误。复核标准距离时优先把相机移到 45–60 cm，不要靠放宽角点或误差阈值掩盖无效深度。
