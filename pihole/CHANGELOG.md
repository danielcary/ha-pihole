# Changelog

## 2026.09.0

- Initial custom Home Assistant app package for official Pi-hole Docker 2026.09.0.
- ARM64 (including Raspberry Pi 5) and AMD64 support.
- DNS on TCP/UDP 53, admin page on host port 4865, and persistent Pi-hole data.
- Cold backups for consistent database copies (briefly pauses DNS).
- DHCP and NTP disabled; only SETFCAP requested for upstream's non-root daemon
  startup, with no host networking or network administration capability.
