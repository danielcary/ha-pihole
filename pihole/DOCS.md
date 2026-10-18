# Installation and setup

This is a custom Home Assistant app that runs Pi-hole's official Docker image
directly. No Pi-hole fork, custom executable, or rebuilt container is involved.
It is not an officially endorsed Home Assistant or Pi-hole app.

## Requirements

- Home Assistant OS with an up-to-date Supervisor. The package is validated
  against Supervisor **2026.10.2** and uses its `data` folder mapping feature.
- A Raspberry Pi 5 (`aarch64`), or an `amd64` Home Assistant OS machine.
- A reserved/static LAN IP for Home Assistant.
- Host port **53 available for both TCP and UDP**. Another DNS app such as
  AdGuard Home cannot use those same ports at the same time.

Z-Wave and WireGuard can continue to run alongside this app. A port conflict
with any service still needs to be resolved before starting Pi-hole.

The only explicitly requested Linux capability is `SETFCAP`: Pi-hole's
official entrypoint uses it to prepare its non-root DNS daemon. No `NET_ADMIN`,
host networking, or access to Home Assistant configuration is requested.

## Install locally

1. Copy this repository's **`pihole` folder** into Home Assistant's `local_apps`
   Samba share (`addons` on older installations). In the official Terminal &
   SSH app the corresponding folder is `/local_apps/pihole`. The resulting
   file should be `local_apps/pihole/config.json`. This is separate from your
   Home Assistant `config` share.
2. In **Settings → Apps → App store** (called **Add-ons** on older versions),
   use the store menu to check for updates/reload. Find **Pi-hole** under
   **Local apps** and install it. Advanced Mode in your user profile may be
   needed to show local developer apps.
3. In the app's **Configuration → Network**, leave both DNS host ports at `53`.
   The web port defaults to `4865`; change that host port if it is occupied.
   Leave Protection mode enabled.
4. Start the app. Allow the first blocklist download to finish. Open **Logs**
   and find the randomly generated admin password. Do not share that log line.
5. Choose **Open Web UI**, sign in, and set your own password in Pi-hole's
   settings. The password is stored in Pi-hole's persistent configuration.
6. Choose upstream resolvers in Pi-hole's DNS settings. Use independently
   reachable resolvers, such as `1.1.1.1` and `1.0.0.1`, or your preferred DNS
   provider. **Do not use your router as an upstream if it forwards DNS back to
   Pi-hole**, and do not point Pi-hole at its own address.
7. Enable **Start on boot** and **Watchdog** on the app's Info page. The
   watchdog checks the admin web server; the official image also includes a
   DNS health check. Test DNS explicitly before changing your router.

Pi-hole is configured through its own web interface. There are no app options
to duplicate those settings. Home Assistant supplies the container's timezone.
DNS listening mode, web server port, DHCP, and NTP are fixed by this package
and appear read-only in Pi-hole.

## Test one device first

From a laptop on your LAN, substitute your Home Assistant IP:

```sh
nslookup example.com 192.0.2.10
dig @192.0.2.10 example.com
dig +tcp @192.0.2.10 example.com
```

Use whichever tools are installed on your laptop. Both UDP and TCP should
resolve. Confirm the query appears in Pi-hole's Query Log. Add a temporary
denylist entry for a test domain through Pi-hole, query it again, and confirm
the Query Log marks it blocked; then remove the temporary entry.

## Router DNS

1. Save your router's current DNS settings so you can restore them.
2. Prefer the router's **LAN/DHCP DNS server** setting: advertise Home
   Assistant's reserved LAN IP as the DNS server to clients. Some routers
   instead proxy DNS and let you set their upstream DNS to this IP; that also
   works, but Pi-hole may identify all queries as coming from the router.
3. Do not enter `:53` or `:4865` in the router DNS field—enter the IP only.
4. Avoid adding a public resolver as a secondary DNS server if all queries
   should be filtered. Clients can use either advertised resolver. For
   redundancy, use a second filtering DNS server on another device.
5. Renew clients' DHCP leases or reconnect them, and confirm their queries
   appear in Pi-hole. If the router advertises IPv6 DNS separately, configure
   that too so it does not advertise an alternative resolver that bypasses
   Pi-hole. Verify IPv6 behavior on your network; this package's primary
   installation path uses the Pi's reserved IPv4 address.

Keep Home Assistant OS's own DNS able to resolve names while Pi-hole is
stopped. In **Settings → System → Network**, use explicit independent DNS
resolvers if automatic DNS would send Home Assistant back to this Pi-hole
via the router. This avoids circular DNS during app installation or recovery.

If Pi-hole or the Pi stops, clients using it lose DNS until it returns. To
recover, restore the router's previous DNS setting and renew client leases.
Do not forward DNS port 53 or admin port 4865 from the Internet to this app.

## WireGuard

For VPN clients to use filtering, set their WireGuard DNS to the Pi's LAN IP
and ensure the tunnel routes that IP and permits TCP/UDP 53. This app does
not change WireGuard peers, routing, or firewall rules.

## Persistence and backups

Supervisor's private app data directory is mounted at `/etc/pihole`. It stores
Pi-hole's configuration, password hash, lists, and query database across
container recreation and updates. Include this app in Home Assistant backups.
The app uses a **cold backup**: Supervisor briefly stops Pi-hole to copy its
databases consistently, then starts it again. DNS is unavailable through this
Pi during that backup, so schedule backups appropriately or provide another
filtering DNS server. For an additional portable copy, use Pi-hole's
**Teleporter** export. Before important changes, make and retain a backup.
Removing the app and its data is different from restarting it.

## Updating Pi-hole

The current app uses `pihole/pihole:2026.09.0`. The app version equals the
upstream Docker tag because Supervisor uses it to select
`pihole/pihole:<version>`. It never tracks the moving `latest` tag. A new
upstream release is not installed until this package is updated to that release.

Pi-hole's Docker software is updated by replacing the container with a newer
official image. Do not run `pihole -up` inside the app. Updating blocklist data
is separate from updating the Pi-hole software.

### Install a published app update

1. Make a Home Assistant backup that includes Pi-hole, and retain it before
   installing a new version.
2. If installed from a Git repository, check for updates in the app store after
   the repository maintainer publishes the new package version. For a **Local
   apps** installation, copy the updated `pihole/` folder over the same local
   folder, then refresh/check for updates in the app store.
3. Open Pi-hole's app Info page and choose **Update** when the new version is
   offered. Supervisor downloads the new official image and replaces the
   container while preserving its private data. DNS pauses during the restart.
4. Check the logs, sign in to Pi-hole, and verify both DNS resolution and
   blocking from a client.

Pushing this project to GitHub or adding its URL to the app store does not
convert an already installed local app to a repository app. Keep using the
local update procedure for that installation. Do not uninstall a working app
just to obtain updates; a source migration requires a separate backup/restore
plan because repository apps have a different Supervisor identity.

No automated upstream monitoring or version-bump service is configured here.
Home Assistant's automatic app updates, if enabled, can only install versions
that this repository has published.

### Maintain a new Pi-hole release

1. Read the official Docker and Pi-hole component release notes and check that
   the new image still supports the app's declared architectures.
2. Set `version` in `pihole/config.json` to the exact official Docker release
   tag. Update the changelog, documented version, and any configuration required
   by that release.
3. Run `python3 tests/verify.py` with Docker. Record the tested image digests and
   results in `VALIDATION.md`. These checks exercise the current host's
   architecture and container recreation; they do not replace testing an
   upgrade of a backed-up Home Assistant installation with existing data.
4. Commit and push the reviewed package. Existing local installations need the
   updated folder copied manually; repository installations can discover it
   through the app store.

## Troubleshooting

- **Port 53 is already allocated:** stop or reconfigure the other DNS service.
  Router DNS requires port 53, so changing Pi-hole to another DNS host port
  does not meet the normal router setup.
- **Admin page unavailable:** check logs and the configured host web port.
  This page opens directly on your LAN and requires its own Pi-hole login.
  It is not embedded through Home Assistant ingress or exposed by Home
  Assistant remote access. Use your WireGuard tunnel for remote access.
- **DNS works but blocking does not:** verify the query reaches Pi-hole,
  gravity lists downloaded, and no alternative IPv6/secondary/encrypted DNS
  is being used by that client. DNS blocking cannot remove every kind of ad.
- **Internet names fail after router changes:** restore the old router DNS,
  check Pi-hole upstreams for a forwarding loop, and check both port mappings.

## Upstream references

- [Official Pi-hole Docker documentation](https://docs.pi-hole.net/docker/)
- [Official Pi-hole Docker configuration](https://docs.pi-hole.net/docker/configuration/)
- [Official Pi-hole Docker updates](https://docs.pi-hole.net/docker/upgrading/)
- [Pi-hole Docker 2026.09.0 release](https://github.com/pi-hole/docker-pi-hole/releases/tag/2026.09.0)
- [Home Assistant app configuration](https://contributors.home-assistant.io/apps/reference/configuration/)
