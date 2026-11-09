#!/usr/bin/env bash
# Usage: smoke-test.sh PROGRAM
# Launches the packaged program offscreen, checks that it stays alive and that the
# port accepts a connection, then stops it. Exit code 0 means the program serves.
set -u
program="${1:?usage: smoke-test.sh PROGRAM}"
port=2048  # fixed in nexplorer/__main__.py
wait_seconds=8

if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    echo "smoke-test: port $port is already in use; stop the other instance first" >&2
    exit 2
fi

export QT_QPA_PLATFORM=offscreen
# Own settings file location, so a test run never touches the user's settings.
home="$(mktemp -d)"
export HOME="$home" XDG_CONFIG_HOME="$home/.config" APPDATA="$home"
log="$home/output.log"

"$program" >"$log" 2>&1 &
pid=$!
cleanup() {
    kill "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    rm -rf "$home"
}
trap cleanup EXIT

status=1
for _ in $(seq 1 "$wait_seconds"); do
    sleep 1
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "smoke-test: program exited at start" >&2
        cat "$log" >&2
        exit 1
    fi
    if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
        status=0
        break
    fi
done

if [ "$status" -ne 0 ]; then
    echo "smoke-test: port $port never accepted a connection" >&2
    cat "$log" >&2
    exit 1
fi

# Stays alive a little after the first connection.
sleep 2
if ! kill -0 "$pid" 2>/dev/null; then
    echo "smoke-test: program died after start" >&2
    cat "$log" >&2
    exit 1
fi
echo "smoke-test: ok ($program serves on port $port)"
