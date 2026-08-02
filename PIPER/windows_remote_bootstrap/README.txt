PIPER Windows remote bootstrap v0.2.2 (offline OpenSSH edition)

Run install_piper_remote.ps1 once from an elevated Windows PowerShell.

It installs/configures:
- bundled Microsoft Win32-OpenSSH when the Windows capability is unavailable
- Windows OpenSSH Server listening only on 127.0.0.1
- key-only local administrator account: piper_remote
- access to C:\Desktop\PIPER and the existing Python 3.12 runtime
- SYSTEM startup task: PIPER Remote Tunnel
- reverse tunnel: server 127.0.0.1:22022 -> Windows 127.0.0.1:22

The tunnel key cannot open a server shell and can listen only on server port 22022.
No Windows or server password is stored in this package.

Server-side recovery:
- Run `python3 PIPER/windows_remote_bootstrap/recover_server_tunnel.py` when
  `ssh piper-windows` times out even though the Windows task says Running.
- The tool checks for a real SSH banner before acting. It only terminates an
  `sshd` child that owns a stale port-22022 listener, then waits for the Windows
  scheduled task to reconnect.

Repository note:
- tunnel_ed25519, operator_authorized_keys, known_hosts, and generated
  piper_windows_remote_bootstrap_v*.zip bundles are deployment-specific.
- They are intentionally excluded from Git. Generate a fresh key pair and
  known-hosts file before packaging a new machine.
- Excluding these source assets does not affect the already-installed Windows
  service under C:\ProgramData\PiperRemote.
