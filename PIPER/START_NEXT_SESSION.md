# PIPER 下次会话快速恢复

当前进度已保存至 2026-08-09：PIPER-X、原厂夹爪、末端 D455、手眼标定、深度到 Base 坐标链和统一时间戳静态快照均已完成。下一项工作是连续多帧同步记录与法兰位姿插值。

开始前先打开 PIPER 电源，确认 USB-CAN、夹爪线和 D455 USB 线已连接，等待约 5 秒；不要改变 D455 支架的位置或角度。

## 仍是同一台学校服务器

现场打开 PIPER 电源，确认 USB-CAN、夹爪线和 D455 USB 线连接正常，然后在服务器执行：

```bash
cd /renyuanliu/MDE-research
bash PIPER/resume_hardware.sh
```

脚本只读取状态，不会进入 control 或发送动作。它会自动修复陈旧隧道、核对 Windows 主机名并在需要时重启观察任务。预期 preflight 中桥版本为 `0.6.0`、模式为 `observe`、机型为 `piper_x`，D455 序列号为 `260722303168`。

如果隧道和 bridge health 正常，但 preflight 报 `PIPER feedback is not healthy`，先确认机械臂电源和 USB-CAN，再重启只读观察任务：

```bash
ssh piper-windows "powershell -NoProfile -Command \"Stop-ScheduledTask -TaskName 'PIPER Bridge Observe'; Start-Sleep 10; Start-ScheduledTask -TaskName 'PIPER Bridge Observe'\""
```

## 换了学校服务器或 SSH 端口

假设新入口为 `<服务器IP>:<SSH端口>`，先在新服务器执行：

```bash
cd /renyuanliu/MDE-research
bash PIPER/restore_new_server.sh <服务器IP> <SSH端口>
```

脚本会恢复服务器到 Windows 的密钥和 SSH 别名，并打印一条 PowerShell 命令。在硬件 Windows 电脑的管理员 PowerShell 中执行那一条命令即可；脚本已经预装在：

```text
C:\ProgramData\PiperRemote\repoint_piper_tunnel.ps1
```

不需要重新下载文件、不需要重新安装 OpenSSH，也不需要把服务器密码写进脚本。端口变化后，Windows 必须知道新目标，因此这一条本机 PowerShell 是唯一无法省略的迁移动作。

服务器登录 Windows 所需的私钥备份位于 `PIPER/.server_recovery/`，权限为 `700/600`，不会进入 Git。更换环境时必须继续挂载当前 `/renyuanliu/MDE-research` 工作区；如果只拿到一次全新 Git clone，需要从受保护存储安全复制该目录，不能把私钥提交到仓库。

完成后回到服务器执行：

```bash
bash PIPER/resume_hardware.sh
```

## 关键结果与下一步

- 手眼 Park 留出误差：`3.660 mm / 0.663°` RMS。
- 深度链 Base 一致性：`3.469 mm / 0.513°`。
- 静态同步快照：法兰反馈与曝光时间差 `5.420 ms`。
- Base 点云：`308,677` 点，约 `90.6%` 位于桌面高度 ±3 cm。
- 相机支架不能松动；松动后必须重新标定。
- 下一步：连续多帧记录 → 相邻法兰位姿插值 → 透明物体 mask/位姿 → 抓取候选与闭环。

完整历史、踩坑和故障处理见 [`HANDOFF_2026-08-02.md`](HANDOFF_2026-08-02.md)。
