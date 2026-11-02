#!/usr/bin/env bash
# The running services, hidden and idle.
S=$(dirname "$0"); source <(sed -n "/^tick=/,/^now()/p" "$S/bench.sh"); OUT=$S/bench-services.txt; : > $OUT
for n in nyx-control-center nyx-notification-center nyx-notifyd; do
  P=$(pgrep -f "^$HOME/.local/bin/$n$" | head -1); [ -n "$P" ] && sample "$n (hidden)" $P 30 &
done
Q=$(pgrep -f "quickshell.*omarchy/shell" | head -1); [ -n "$Q" ] && sample "omarchy-shell (for comparison)" $Q 30 &
wait
