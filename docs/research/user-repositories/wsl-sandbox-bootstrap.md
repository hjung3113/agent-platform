# wsl-sandbox-bootstrap

Status: PLATFORM REFERENCE

Evidence:
- README: WSL host -> validated export -> Docker sandbox, profile inheritance,
  non-root UID/GID alignment, company integration hooks, Herdr integration docs.

Adopt:
- optional platform bootstrap profile
- controlled host->sandbox config export
- environment validation

Do not couple:
- core workflow must not require WSL/Docker.
