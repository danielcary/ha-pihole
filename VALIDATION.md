# Validation

Validated on **2026-10-17** using Docker Desktop on ARM64 macOS, running Linux
ARM64 containers. Run `python3 tests/verify.py` to repeat the checks.
The complete container verification passed again on **2026-10-18** with the
same release versions.

## Images

| Image | Upstream registry manifest digest observed during validation |
| --- | --- |
| `pihole/pihole:2026.09.0` | `sha256:5b9c8cf51de7d6d3f2240dbe72baf5f06e1fd39cb4d77a99fab4fa13e23bd1be` |
| `ghcr.io/home-assistant/aarch64-hassio-supervisor:2026.10.2` | `sha256:9054854b6da9b4f667430e69107c812832e65e575a0dc63be89d750cd4b70d47` |

These digests record the images tested. Supervisor selects the Pi-hole image
by the fixed release tag in `config.json`, not by this recorded digest.
The upstream Pi-hole manifest advertises both ARM64 and AMD64; the runtime
checks here exercised ARM64 only.

## Passed

- The released Supervisor's own schema accepts the app and repository metadata
  without discarding any app keys, including the persistent private data mapping.
- The official Pi-hole image starts with Supervisor's reduced default capability
  set plus explicit `SETFCAP`; `NET_ADMIN`, `NET_RAW`, and `SYS_TIME` are absent.
- Pi-hole's built-in DNS health check and the published admin page become ready.
- First boot generates an admin password, and it authenticates through Pi-hole's API.
- The manifest's bridge listening mode and disabled DHCP/NTP settings take effect.
- Native API changes set DNS upstreams, a local DNS record, and a new password.
- Queries through published localhost **UDP and TCP** ports resolve both the
  configured local record and an Internet domain.
- A domain added to the exact denylist returns a blocked response.
- Pi-hole stops cleanly with exit code 0, and replacing the container while
  keeping its data preserves the password, local record, upstreams, and denylist.
- Disposable test containers and their data volume are removed after the run.

The test accommodates Pi-hole's asynchronous DNS restart after API changes.
No credentials or user network settings are included in the package.

## Home Assistant OS acceptance

The **2026.09.0** app was checked on a physical Raspberry Pi 5 running
Home Assistant OS. Installation, admin access, operation after a full
reboot, and LAN DNS responses over UDP and TCP were verified.

## Remaining acceptance checks

The test imports the official Supervisor's schema in a container; it does not
boot Supervisor services or emulate Home Assistant OS. Confirm
backup/restore and DNS distribution on your network. See the
[installation guide](pihole/DOCS.md) for those checks.

Cold backup behavior is declared in the manifest and accepted by Supervisor's
schema, but a full Supervisor-managed backup/restore has not been exercised here.
