# Chromium seccomp profile

Vendored from Microsoft Playwright v1.64.1, Apache-2.0:
https://raw.githubusercontent.com/microsoft/playwright/v1.64.1/utils/docker/seccomp_profile.json

SHA-256: `cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849`.

Docker default-deny syscall policy with Chromium user-namespace support.
Never replace this with an unconfined seccomp policy or disable the browser sandbox.

Local adjustment: allow the `chroot` syscall needed inside Chromium's private user namespace when all container capabilities are dropped. This does not grant a host capability; Linux still enforces namespace capability checks.

Local SHA-256: `ff6bb3f90c3b5ed7c41a3ddfa2cfd319e1f30eda2120fee232880ad7087edab7`.
