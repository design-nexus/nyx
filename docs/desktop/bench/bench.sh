#!/usr/bin/env bash
# Nyx Desktop measurements. Test copies on HEADLESS-20 only, never focused.
# Usage: bench.sh <label> <idle seconds>. Test windows live on special (virtual) workspaces only.
set -u
LABEL=$1; IDLE=${2:-30}; S=$(dirname "$0"); OUT=$S/bench-$LABEL.txt; : > $OUT
tick=$(getconf CLK_TCK)
say() { echo "$*" | tee -a $OUT; }
cpu() { awk -v t=$tick '{print ($14+$15)/t}' /proc/$1/stat 2>/dev/null || echo 0; }
ctx() { local s=0; for t in /proc/$1/task/*; do s=$((s + $(awk '/^(non)?voluntary_ctxt_switches/ {a+=$2} END {print a+0}' $t/status 2>/dev/null || echo 0))); done; echo $s; }
mem() { awk '/^Rss:/ {r=$2} /^Pss:/ {p=$2} /^Private_(Clean|Dirty):/ {v+=$2} END {printf "RSS %.0f MiB, PSS %.0f MiB, private %.0f MiB", r/1024, p/1024, v/1024}' /proc/$1/smaps_rollup; }
# GPU buffers this process holds (per DRM client, counted once).
gpu() { local t=0; declare -A seen; for f in /proc/$1/fdinfo/*; do id=$(awk '/^drm-client-id:/ {print $2}' $f 2>/dev/null); [ -z "$id" ] && continue; [ -n "${seen[$id]:-}" ] && continue; seen[$id]=1; kb=$(awk '/^drm-total-(system|local|vram)[0-9]*:/ {v=$2; u=$3; if (u=="MiB") v*=1024; if (u=="GiB") v*=1048576; s+=v} END {print s+0}' $f); t=$((t + ${kb%.*})); done; echo "GPU $((t/1024)) MiB"; }
sample() { # name pid seconds
  local c0=$(cpu $2) w0=$(ctx $2); sleep $3; local c1=$(cpu $2) w1=$(ctx $2)
  say "$1: $(mem $2), $(gpu $2); idle ${3}s: CPU $(awk -v a=$c0 -v b=$c1 'BEGIN{printf "%.2f", b-a}') s, wakeups $(( (w1-w0) / $3 ))/s"
}
mapped() { hyprctl layers -j | jq -e --arg n "$1" '.["HEADLESS-20"].levels[][] | select(.namespace==$n)' >/dev/null 2>&1; }
now() { date +%s%N; }

say "== $LABEL: HEADLESS-20 $(hyprctl monitors -j | jq -r '.[] | select(.name=="HEADLESS-20") | "\(.width)x\(.height) @\(.scale)"')"

# Dock: idle, then how fast it notices a window arriving on its screen.
NYX_DOCK_DEBUG=1 nyx-dock --only HEADLESS-20 2> >(while IFS= read -r l; do echo "$(date +%s%N) $l"; done > $S/dock-$LABEL.log) & D=$!
sleep 6
sample "dock (shown)" $D $IDLE
hyprctl eval 'hl.exec_cmd("[workspace special:nyxbench silent; noinitialfocus] foot --app-id=nyx-bench sleep 120")' >/dev/null
sleep 1.5
A=$(hyprctl clients -j | jq -r '.[] | select(.class=="nyx-bench") | .address' | head -1)
lat=()
for i in 1 2 3 4 5 6; do
  ws=$([ $((i % 2)) = 1 ] && echo special:nyxbench2 || echo special:nyxbench)
  n0=$(wc -l < $S/dock-$LABEL.log); t0=$(now)
  hyprctl eval "hl.dispatch(hl.dsp.window.move({ workspace = \"$ws\", follow = false, window = \"address:$A\" }))" >/dev/null
  for _ in $(seq 100); do
    line=$(tail -n +$((n0+1)) $S/dock-$LABEL.log | grep -m1 "HEADLESS-20: .* items")
    [ -n "$line" ] && break; sleep 0.01
  done
  [ -n "$line" ] && lat+=( $(( (${line%% *} - t0) / 1000000 )) )
  sleep 0.6
done
say "dock: window arrives/leaves -> dock redrawn: ${lat[*]} ms"
hyprctl dispatch "hl.dsp.window.close({ window = \"address:$A\" })" >/dev/null
kill $D; wait $D 2>/dev/null

# Panels: cold start to on screen, then shown and idle.
for p in "control-center:NYX_CC_NO_KEYBOARD:nyx-control-center" "notification-center:NYX_NC_NO_KEYBOARD:nyx-notification-center"; do
  IFS=: read name env ns <<<"$p"
  t0=$(now); env $env=1 nyx-$name --only HEADLESS-20 --show >/dev/null 2>&1 & P=$!
  for _ in $(seq 300); do mapped $ns && break; sleep 0.01; done
  say "$name: start to on screen $(( ($(now) - t0) / 1000000 )) ms"
  sleep 4
  sample "$name (open)" $P 10
  kill $P; wait $P 2>/dev/null
done
