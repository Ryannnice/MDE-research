#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ssh_options=(-o BatchMode=yes -o ConnectTimeout=5 piper-windows)
python_windows='C:\Desktop\PIPER\remote_control\.venv\Scripts\python.exe'
client_windows='C:\Desktop\PIPER\remote_control\piper_client.py'
bridge_url='http://127.0.0.1:57846'
health_command="$python_windows $client_windows --url $bridge_url health"
preflight_command='C:\Desktop\PIPER\camera\.venv\Scripts\python.exe C:\Desktop\PIPER\handeye\handeye_calibration.py preflight'

echo "Checking the reverse tunnel..."
python3 "$project_dir/windows_remote_bootstrap/recover_server_tunnel.py"

windows_host=$(ssh "${ssh_options[@]}" hostname | tr -d '\r')
[[ $windows_host == ENVY_Katana ]] || {
    echo "Unexpected Windows host: $windows_host" >&2
    exit 1
}
echo "Windows reachable: $windows_host"

if ! ssh "${ssh_options[@]}" "$health_command"; then
    echo "Observe bridge is unavailable; restarting its read-only scheduled task..."
    ssh "${ssh_options[@]}" \
        "powershell -NoProfile -Command \"Stop-ScheduledTask -TaskName 'PIPER Bridge Observe' -ErrorAction SilentlyContinue; Start-Sleep 10; Start-ScheduledTask -TaskName 'PIPER Bridge Observe'\""

    bridge_ready=false
    for _ in 1 2 3 4 5 6; do
        sleep 5
        if ssh "${ssh_options[@]}" "$health_command"; then
            bridge_ready=true
            break
        fi
    done
    [[ $bridge_ready == true ]] || {
        echo "Observe bridge did not recover. Check PIPER power, USB-CAN, and C:\\ProgramData\\PiperRemote\\bridge-observe.log." >&2
        exit 1
    }
fi

echo "Running read-only PIPER-X and D455 preflight..."
ssh "${ssh_options[@]}" "$preflight_command"
echo "PIPER-X, gripper, observe bridge, and D455 are ready. No motion command was sent."
