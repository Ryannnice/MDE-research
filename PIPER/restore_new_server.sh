#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <server-host> <server-ssh-port>" >&2
    exit 2
}

[[ $# -eq 2 ]] || usage
[[ ${EUID} -eq 0 ]] || {
    echo "Run this script as root on the new school server." >&2
    exit 2
}

server_host=$1
server_port=$2
[[ $server_host =~ ^[A-Za-z0-9.-]+$ ]] || {
    echo "Invalid server host: $server_host" >&2
    exit 2
}
[[ $server_port =~ ^[0-9]+$ ]] && ((server_port >= 1 && server_port <= 65535)) || {
    echo "Invalid SSH port: $server_port" >&2
    exit 2
}

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
recovery_dir="$project_dir/.server_recovery"
bootstrap_dir="$project_dir/windows_remote_bootstrap"
operator_key="$recovery_dir/piper_windows_operator_ed25519"
operator_public="$bootstrap_dir/piper_windows_operator_ed25519.pub"
tunnel_public="$bootstrap_dir/piper_windows_tunnel_ed25519.pub"
windows_known_hosts="$bootstrap_dir/piper_windows_known_hosts"
ssh_dir=/root/.ssh

for required in "$operator_key" "$operator_public" "$tunnel_public" "$windows_known_hosts"; do
    [[ -f $required ]] || {
        echo "Missing recovery asset: $required" >&2
        echo "The private recovery directory is intentionally not stored in Git." >&2
        exit 1
    }
done

derived_operator_public=$(ssh-keygen -y -f "$operator_key" | awk '{print $1 " " $2}')
expected_operator_public=$(awk '{print $1 " " $2}' "$operator_public")
[[ "$derived_operator_public" == "$expected_operator_public" ]] || {
    echo "The private recovery key does not match the deployed Windows key." >&2
    exit 1
}

install -d -m 700 "$ssh_dir"
install -m 600 "$operator_key" "$ssh_dir/piper_windows_operator_ed25519"
install -m 644 "$operator_public" "$ssh_dir/piper_windows_operator_ed25519.pub"
install -m 644 "$windows_known_hosts" "$ssh_dir/piper_windows_known_hosts"

authorized_keys="$ssh_dir/authorized_keys"
authorized_keys_tmp=$(mktemp "$ssh_dir/authorized_keys.piper.XXXXXX")
if [[ -f $authorized_keys ]]; then
    awk '$0 !~ /piper-windows-reverse-tunnel[[:space:]]*$/' "$authorized_keys" > "$authorized_keys_tmp"
fi
printf '%s %s\n' \
    'command="/bin/false",restrict,port-forwarding,permitlisten="127.0.0.1:22022"' \
    "$(<"$tunnel_public")" >> "$authorized_keys_tmp"
install -m 600 "$authorized_keys_tmp" "$authorized_keys"
rm -f "$authorized_keys_tmp"

config="$ssh_dir/config"
config_tmp=$(mktemp "$ssh_dir/config.piper.XXXXXX")
if [[ -f $config ]]; then
    awk '
        $0 == "# BEGIN PIPER WINDOWS" { managed = 1; next }
        $0 == "# END PIPER WINDOWS" { managed = 0; next }
        !managed && $0 ~ /^[[:space:]]*Host[[:space:]]+piper-windows([[:space:]]|$)/ {
            legacy = 1
            next
        }
        legacy && $0 ~ /^[[:space:]]*Host[[:space:]]+/ { legacy = 0 }
        !managed && !legacy { print }
    ' "$config" > "$config_tmp"
fi
printf '%s\n' \
    '' \
    '# BEGIN PIPER WINDOWS' \
    'Host piper-windows' \
    '    HostName 127.0.0.1' \
    '    Port 22022' \
    '    User piper_remote' \
    '    IdentityFile /root/.ssh/piper_windows_operator_ed25519' \
    '    IdentitiesOnly yes' \
    '    StrictHostKeyChecking yes' \
    '    UserKnownHostsFile /root/.ssh/piper_windows_known_hosts' \
    '    ServerAliveInterval 5' \
    '    ServerAliveCountMax 3' \
    '# END PIPER WINDOWS' >> "$config_tmp"
install -m 600 "$config_tmp" "$config"
rm -f "$config_tmp"

server_host_key=/etc/ssh/ssh_host_ed25519_key.pub
[[ -f $server_host_key ]] || {
    echo "Missing server ED25519 host key: $server_host_key" >&2
    exit 1
}
server_fingerprint=$(ssh-keygen -lf "$server_host_key" -E sha256 | awk '{print $2}')

echo "New server SSH side is ready."
echo
echo "Run this once in an elevated PowerShell on the hardware Windows PC:"
repoint_script='C:\ProgramData\PiperRemote\repoint_piper_tunnel.ps1'
printf "& '%s' -ServerHost '%s' -ServerPort %s -ExpectedHostKeySHA256 '%s'\n" \
    "$repoint_script" "$server_host" "$server_port" "$server_fingerprint"
echo
echo "Then verify on this server:"
echo "python3 '$project_dir/windows_remote_bootstrap/recover_server_tunnel.py'"
echo "ssh -o BatchMode=yes piper-windows hostname"
