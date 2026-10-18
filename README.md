# Pi-hole for Home Assistant OS

A small Home Assistant app package for **Pi-hole's unmodified official Docker
image**. Point your router's DNS at your Home Assistant Pi's LAN IP to use
network-wide DNS filtering.

This repository is custom, not endorsed by Pi-hole or Home Assistant. The
runtime is downloaded directly from `pihole/pihole:2026.09.0`; there is no
Dockerfile, third-party Pi-hole build, or custom startup script.

| Service | Address |
| --- | --- |
| DNS | `HOME_ASSISTANT_IP:53` over UDP and TCP |
| Administration | `http://HOME_ASSISTANT_IP:4865/admin/` |
| Persistent data | Supervisor app data mounted at `/etc/pihole` |

Supports Raspberry Pi 5/ARM64 and AMD64. Requires current Home Assistant OS
and Supervisor; validation targets Supervisor 2026.10.2. DHCP and NTP are
disabled. The app requests only `SETFCAP`, which the official entrypoint needs
to configure its non-root DNS daemon. It uses no host networking or Home
Assistant API access. Z-Wave and WireGuard can run alongside it.

## Install

Copy `pihole/` into Home Assistant's `local_apps` share (`addons` on older
versions), reload the app store,
and install **Pi-hole** from **Local apps**. Read the generated password in
the app's logs and open the web interface. Test DNS from one device, then
configure the router. Full instructions, backup details, and recovery steps
are in [the installation guide](pihole/DOCS.md).

Alternatively, add **https://github.com/danielcary/ha-pihole** in
**App store → Repositories**, then install Pi-hole from this repository.
Adding the repository does not change an existing local installation's update
source; see the update instructions below before migrating an installed app.

## Updates

The app pins the official Pi-hole image to **2026.09.0**. New Pi-hole software
does not install automatically just because upstream publishes a release. The
repository maintainer must update the image version and test it first.

For an app installed from this repository, Home Assistant then offers the new
version on the app's Info page. For an existing **Local apps** installation,
copy the updated `pihole/` folder over the existing local folder and refresh the
app store before updating. Keep the app installed so its saved data remains in
place. Back up before updating; DNS briefly stops while the container restarts.
See [the update guide](pihole/DOCS.md#updating-pi-hole) for the complete workflow.

## Verify with Docker

```sh
python3 tests/verify.py
```

Requires Python 3 and a running Docker engine with Internet access. It validates
the manifest inside the **official Home Assistant Supervisor** container, then
runs the **official ARM64/AMD64 Pi-hole** container on temporary localhost ports.
It tests UDP/TCP DNS, upstream resolution, authenticated API access, blocking,
container recreation with saved configuration and password, and clean shutdown.
Temporary containers and volumes are removed afterward. It does not alter
your Mac's DNS or your router.

The test does not boot Home Assistant OS or its Supervisor services. Installing
the app on an actual Home Assistant OS device remains a separate acceptance
check. See [validation notes](VALIDATION.md) for the recorded results.

Co-authored by Codex.
