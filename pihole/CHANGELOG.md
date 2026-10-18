# Changelog

## 2026.10.0

- Update to the unmodified official Pi-hole Docker 2026.10.0 image, containing
  FTL v6.8, Web v6.6.1, and Core v6.5, with upstream security and bug fixes.
- Keep the existing port mappings, persistent data mapping, and capabilities.
- Add an optional previous-version upgrade check to the Docker validation.

## 2026.09.0

- Initial custom Home Assistant app package for official Pi-hole Docker 2026.09.0.
- ARM64 (including Raspberry Pi 5) and AMD64 support.
- DNS on TCP/UDP 53, admin page on host port 4865, and persistent Pi-hole data.
- Cold backups for consistent database copies (briefly pauses DNS).
- DHCP and NTP disabled; only SETFCAP requested for upstream's non-root daemon
  startup, with no host networking or network administration capability.
