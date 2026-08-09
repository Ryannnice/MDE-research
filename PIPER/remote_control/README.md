# PIPER 安全远程桥

这个目录把远程推理与本地 CAN 控制隔开：服务器提交高层关节目标，Windows 电脑负责实时反馈、轨迹分段、关节限位、现场许可和电子急停。

## 不可绕过的安全规则

- 第一次启动只能使用 `start_observe.ps1`；观察模式没有使能或运动代码路径。
- 实机运动前，现场人员必须清空整个工作空间，并能立即操作实体急停或安全断电。
- 控制模式仍默认拒绝动作。现场人员在桥接窗口输入一次 `ARM WORKSPACE CLEAR` 后，许可持续到 `DISARM`、`STOP` 或桥接程序退出，不需要定时续期。
- 运动前必须单独执行 `prepare`；它只选择配置的低速 CAN/MOVE J 模式并等待状态反馈，不发送关节目标。
- 一条高层命令可以覆盖完整官方关节范围；客户端会自动拆成不超过 2° 的连续航点，桥仍逐航点核对新鲜反馈和 3° 内部步长。
- 默认速度上限为 5%，可在现场启动控制桥时用 `-MaxSpeedPercent 1..100` 配置；远程指令不能超过本次启动值。
- 机械臂运动超时或反馈故障会发送 SDK 的阻尼电子急停；夹爪动作超时或反馈故障只会失能夹爪驱动。故障后不自动复位。
- 退出空闲桥接程序不会自动失能，因为突然失能可能让机械臂下落。退出运动中的桥接程序会尝试电子急停。
- 当前阶段不开放机械臂 `reset`、远程关节失能、MIT 模式、笛卡尔运动或原始 CAN 帧。

## 夹爪与相机连接

- 原厂 AGILE.X 两指夹爪接机械臂末端预留的夹爪线束，由机械臂的 24 V/CAN 链路通信；不要把夹爪接到 D455。
- Intel RealSense D455 通过 USB 3.x 直接接 Windows 电脑，不与机械臂做电气连接。机械臂状态和 RGB-D 帧后续通过时间戳及手眼标定在软件中对齐。
- 当前 D455 已固定在末端附近（eye-in-hand）。相机仍通过 USB 3.x 直接连接 Windows；运动前必须确认 USB 线具有应力释放并避开全部关节和夹爪。

夹爪接线完成后，先以只读方式启动；观察模式没有任何夹爪动作路径：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_observe.ps1 -Firmware v189 -Gripper agx
```

`gripper.feedback_present: true`、`gripper.healthy: true` 且所有 `gripper.faults` 为 `false`，才表示反馈链路通过。`driver_enabled` 或 `homed` 为 `false` 会单独显示，并不会被伪装成通信故障。若夹爪并非原厂 AGILE.X 型号，请保持 `-Gripper none`。

从桥 v0.6.0 开始，`state.arm.flange_pose_m_rad` 提供机械臂基座坐标系中的法兰反馈位姿 `[x, y, z, roll, pitch, yaw]`（m/rad），供眼在手上标定使用；`flange_pose_fk_m_rad` 是用同一组反馈关节角计算的离线 FK 交叉检查。对应的反馈频率和新鲜度分别为 `flange_feedback_hz` 与 `flange_feedback_age_s`。当前实机已由“控制器末端反馈与各候选机型 FK”交叉核验为 `piper_x`，三份 Windows 启动脚本均默认使用该机型；切勿改回普通 `piper`，否则手眼标定位姿会明显错误。

### 夹爪标定与宽度控制

控制桥支持原厂夹爪的 0–70 mm 宽度模式和 0–3 N 力参数。未回零时，桥会拒绝所有宽度动作。标定会把夹爪当时的位置解释为零点，因此必须严格按以下顺序执行：

1. 确认 `driver_enabled: false`，然后手动把两指轻推到完全闭合。
2. 启动控制桥、输入一次现场许可，并执行 `prepare`；它不会移动机械臂。
3. 显式确认完全闭合并标定。
4. 先以 0.5 N 张开到 10 mm，核对反馈后再使用更大行程。

```bash
python3 piper_client.py prepare
python3 piper_client.py gripper-calibrate --confirm-fully-closed --execute
python3 piper_client.py gripper-move --width-mm 10 --force-n 0.5
python3 piper_client.py gripper-move --width-mm 10 --force-n 0.5 --execute
python3 piper_client.py gripper-disable --execute
```

不带 `--execute` 时只预览。每条动作会绑定刚读取的实际开口，目标超时、反馈过期或出现故障位时会失能夹爪。空夹爪宽度定位完成后，再单独标定有物体接触时的抓取完成判据。

部分 S‑V1.8‑9 控制器在成功响应零点写入并把开口读回为 0 mm 后，仍不置位 `homed` bit。桥只在“本次连接收到成功 ACK + 随后读回零点”两项同时满足时建立会话级零点锁存；桥重启后该锁存自动失效，并要求重新确认。

## Windows 安装

要求：Windows 10/11、64 位 Python 3.11/3.12、随臂官方 USB-CAN。CAN 波特率由驱动固定为 1 Mbps。

在普通 PowerShell 中进入本目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
```

脚本会建立 `.venv`，并从本目录 `vendor/` 的离线源码包安装固定提交的官方组件，不依赖 Windows 访问 GitHub：

- `agilexrobotics/pyAgxArm@799b8412fbe8b9156bc9892d3dbeb2df7e98be71`
- `agilexrobotics/python-can-agx-cando@b222c4027ad4f6599f7634c72c67184619177972`

如果目录中没有 `session-token.txt`，安装脚本会生成一个。Windows 和服务器必须使用同一个文件。

## 第一次只读连接

当前 PIPER-X、固件不明时先运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_observe.ps1
```

脚本默认 `-Model piper_x`；若把同一套代码用于其他实机，必须显式指定正确的 `-Model piper`、`piper_h` 或 `piper_l`。固件档位：

| 主控固件 | 参数 |
|---|---|
| `<= S-V1.8-2` | `default` |
| `S-V1.8-3` 至 `S-V1.8-7` | `v183` |
| `S-V1.8-8` | `v188` |
| `>= S-V1.8-9` | `v189` |

只读成功时窗口会打印 `connected: true`、六个 `joint_angles_rad`、`arm_status: NORMAL`、`err_code: 0` 和固件信息，然后显示：

```text
PIPER bridge ready on http://127.0.0.1:<LOCAL_PORT> (observe mode)
```

## 反向 SSH 隧道

保持桥接窗口运行，另开一个 Windows PowerShell。把 `<学校服务器>` 换成 VS Code Remote-SSH 使用的主机别名：

```powershell
ssh -NT `
  -R 127.0.0.1:8765:127.0.0.1:<LOCAL_PORT> `
  -o ExitOnForwardFailure=yes `
  -o ServerAliveInterval=5 `
  -o ServerAliveCountMax=3 `
  <学校服务器>
```

服务器端随后只能通过自己的 `127.0.0.1:8765` 访问本地桥；不需要开放 Windows 防火墙端口或路由器端口。

## 服务器核验

```bash
python3 piper_client.py health
python3 piper_client.py state
```

模拟测试：

```bash
python3 -m unittest discover -s tests -t . -v
```

## 控制阶段

只在观察数据核验完成后关闭观察桥，运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_control.ps1 -Firmware v189 -Gripper agx
```

如实验确实需要更高速度，由现场启动时显式设置，例如：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_control.ps1 -Firmware v189 -MaxSpeedPercent 20
```

桥接器重启后通常会得到新的 `<LOCAL_PORT>`；同时重启 SSH 隧道，并把转发目标改成这个新端口。

现场清场后，在同一窗口输入：

```text
ARM WORKSPACE CLEAR
```

服务器先执行无目标的控制模式准备，确认 `ctrl_mode` 变为 `CAN_CTRL`，然后使能并预览动作：

```bash
python3 piper_client.py prepare
python3 piper_client.py enable
python3 piper_client.py state
python3 piper_client.py move-relative --joint 6 --degrees 1
```

预览不会运动；只有显式增加 `--execute` 才提交。现场或服务器均可发送电子急停，现场窗口直接输入 `STOP`，服务器运行：

```bash
python3 piper_client.py stop
```

`move-relative`、`move-absolute` 和 `cycle-absolute` 都接受跨完整合法关节范围的高层目标，并自动分段。循环次数只要求为正整数，不再限定最多三次。执行前会先验证最终目标，避免运动到一半才发现越限。桥不会关闭 SDK 关节限位或静默保留越限目标。

## 官方依据

- [pyAgxArm Windows 与 PIPER 支持](https://github.com/agilexrobotics/pyAgxArm)
- [Windows `agx_cando` 插件](https://github.com/agilexrobotics/python-can-agx-cando)
- [CAN 模块说明](https://github.com/agilexrobotics/pyAgxArm/blob/master/docs/can_user.md)
