#!/usr/bin/env bash
# Build an immutable source snapshot, then publish to an existing website target.
set -Eeuo pipefail
task_source=$(cd -P -- "$(dirname -- "$0")" && cd .. && pwd -P)
task_root=${CIRDC_WEB_ROOT:?Set CIRDC_WEB_ROOT to the existing website deployment root}
task_state=${CIRDC_WEB_STATE:-$task_root/.runtime/state}
task_release=${1:-web-$(date -u +%Y%m%dT%H%M%SZ)}
[[ "$task_release" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || { echo 'Invalid release identifier' >&2; exit 1; }
[[ "$task_root" = /* && "$task_state" = /* ]] || { echo 'Absolute deployment paths are required' >&2; exit 1; }
task_destination="$task_root/releases/$task_release"
task_python="$task_root/.venv/bin/python"
task_control="$task_root/.runtime/deployment"
test -L "$task_root/current" && test -x "$task_python" || {
    echo 'An existing release and website environment are required.' >&2; exit 1;
}
test -s "$task_state/accounts.sqlite" && test -s "$task_state/search.sqlite" || {
    echo 'Existing website accounts and search state are required.' >&2; exit 1;
}
test ! -f "$task_root/.venv/.cirdc-runtime-protected" || {
    echo 'This environment is a protected collection runtime.' >&2; exit 1;
}
install -d -m 0700 "$task_control"
exec 9>"$task_control/release.lock"
flock -n 9 || { echo 'Another website deployment is in progress.' >&2; exit 1; }
task_previous=$(readlink "$task_root/current")
[[ "$task_previous" =~ ^releases/[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || {
    echo 'The current release must be a managed relative release link.' >&2; exit 1;
}
shopt -s nullglob
task_previous_wheels=("$task_root/$task_previous"/dist/cirdc_pro-*.whl)
[[ ${#task_previous_wheels[@]} -eq 1 ]] || { echo 'Exactly one rollback wheel is required.' >&2; exit 1; }
task_previous_wheel=${task_previous_wheels[0]}
test ! -e "$task_destination" && test ! -L "$task_destination"
mkdir "$task_destination"
# Snapshot canonical source, excluding development environments and build caches.
tar -C "$task_source" --exclude=node_modules --exclude=__pycache__ --exclude='*.pyc' \
    -cf - src web docs deploy tools pyproject.toml uv.lock LICENSE README.md README_CN.md \
    AGENTS.md CLAUDE.md .agents .claude .codex .mcp.json config.example.json requirements.txt \
    | tar -C "$task_destination" -xf -
(cd "$task_destination/web" && npm ci --no-audit --no-fund && npm run build)
uv build --wheel --project "$task_destination" --out-dir "$task_destination/dist"
# This directory belongs solely to the candidate release.
rm -rf -- "$task_destination/web/node_modules"
task_wheels=("$task_destination"/dist/cirdc_pro-*.whl)
[[ ${#task_wheels[@]} -eq 1 ]] || { echo 'Exactly one candidate wheel is required.' >&2; exit 1; }
task_wheel=${task_wheels[0]}
# Check installed dependencies before stopping any service. Publication does not
# resolve or upgrade dependencies and does not reinstall private providers.
uv pip check --python "$task_python"
# Loading the existing configuration can touch a remote filesystem. Refuse the
# switch while it is unavailable, instead of leaving restarted services hanging.
timeout --kill-after=5 15 "$task_python" -c 'from cirdc.config import Config; Config.load()'
test "$(readlink "$task_root/current")" = "$task_previous"
task_services=(cirdc-web.service cirdc-admin.service cirdc-index.service)
switch_current() {
    local target=$1
    ln -s "$target" "$task_root/current.switch-$$"
    mv -Tf "$task_root/current.switch-$$" "$task_root/current"
}
install_wheel() {
    uv pip install --offline --python "$task_python" --no-deps --reinstall "$1"
}
health() {
    curl --noproxy '*' --retry 8 --retry-connrefused --retry-delay 1 --max-time 5 \
        --fail --silent http://127.0.0.1:18088/healthz || return
    curl --noproxy '*' --retry 8 --retry-connrefused --retry-delay 1 --max-time 5 \
        --fail --silent http://127.0.0.1:18089/healthz
}
rollback() {
    trap - ERR INT TERM
    set +e
    local failed=0
    systemctl --user stop "${task_services[@]}" || failed=1
    install_wheel "$task_previous_wheel" || failed=1
    switch_current "$task_previous" || failed=1
    systemctl --user start "${task_services[@]}" || failed=1
    health || failed=1
    if [[ "$failed" -eq 0 ]]; then
        echo 'Website deployment failed; previous release restored.' >&2
    else
        echo 'Website deployment failed; rollback needs inspection. Existing release and state retained.' >&2
    fi
    exit 1
}
# Trap before stopping: even a partially failed stop must restore the old release.
trap rollback ERR INT TERM
systemctl --user stop "${task_services[@]}"
install_wheel "$task_wheel"
uv pip check --python "$task_python"
switch_current "releases/$task_release"
# Existing unit files, drop-ins, environment, accounts and index state stay in place.
systemctl --user start "${task_services[@]}"
health
systemctl --user is-active --quiet "${task_services[@]}"
trap - ERR INT TERM
echo "CIRDC_WEB_RELEASE_READY $task_release"
