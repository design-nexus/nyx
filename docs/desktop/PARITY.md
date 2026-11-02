# Bar plugins and what replaces them

Before a bar plugin is removed, everything it does has to be somewhere in Nyx (decision
§9.5 in ARCHITECTURE.md). ✓ done, ◐ partly, ✗ missing. Updated 2026-11-02.

| Plugin | Feature | Where in Nyx | |
| --- | --- | --- | --- |
| **omarchy.network** | Wi-Fi on/off, scan, join (password), signal | Control Center › Wi-Fi | ✓ |
| | DNS provider (Cloudflare, Google, DHCP, custom) | Wi-Fi view › DNS | ✓ |
| | Wi-Fi band (auto / 2.4 / 5 / 6 GHz) | Wi-Fi view › Band (when the network has more than one) | ✓ |
| | Captive-portal sign-in | Wi-Fi view (when NetworkManager reports a portal) | ✓ |
| | Speed test, share by QR | Wi-Fi view footer (Omarchy's own panels) | ✓ |
| | Connection details: IP, gateway, link speed, router and internet ping, throughput | — | ✗ |
| **omarchy.bluetooth** | On/off, paired devices, connect/disconnect, battery | Control Center › Bluetooth | ✓ |
| | Find and pair new devices, forget a device | — | ✗ |
| **omarchy.audio** | Volume, mute, output picker, each app's volume | Sound tile and its popover | ✓ |
| | Scroll on the icon to change volume | Nyx Status (bar) | ✓ |
| | Microphone: input device, level, mute | — | ✗ |
| **omarchy.power** | Power profiles | Power mode tile | ✓ |
| | Battery %, charging, time left | Battery tile, Nyx Status | ✓ |
| | Battery details: rate, size, health/cycles, charge limit | — | ✗ |
| **omarchy.monitor** (Display) | Brightness (laptop, DDC) | Sound tile › brightness (focused screen) | ✓ |
| | Brightness per screen, text size, scale, laptop screen on/off | — | ✗ |
| **omarchy.tailscale** | On/off, sign-in, this machine, machines, copy address/name | Control Center › Tailscale | ✓ |
| | Send files to a machine | Tailscale view | ✓ |
| | Exit node (Mullvad by country), accounts | Tailscale view | ✓ |
| | Search the machine list; Mullvad city picker; receive files | — | ✗ |
| **design-nexus.privacy-route** | Direct / NordVPN / Tor, one at a time, "both on" warning | Control Center › VPN | ✓ |
| | NordVPN country, kill switch, auto-connect | VPN view | ✓ |
| | NordVPN city, pause, technology/protocol | — | ✗ |
| | Tor modes, new circuit, exit back to automatic | VPN view | ✓ |
| | Tor exit country picker, live latency, bridges, Tor browser, panic | — | ✗ |
| **harshith.system-monitor** | CPU and memory at a glance | Nyx Status (bar); click opens Activity | ✓ |
| | GPU, temperatures, network, disk; sparklines panel | Activity app (not at a glance) | ◐ |
| **mryll.meteobar**, **design-nexus.weather** | Temperature at a glance; forecast | Nyx Status; click opens Weather | ✓ |
| **omacal.upcoming** | Upcoming events | — (a Calendar "Up next" tile) | ✗ |
| **ken.nyx-assistant** | Assistant button and state | — | ✗ |
| **ken.omarchy-backup** | Backup status and run | — | ✗ |
| **jankeesvw.notification-center** | Notification history | Nyx Notification Center | ✓ |
