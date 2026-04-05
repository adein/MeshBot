# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in MeshBot, please report it responsibly rather than opening a public issue.

**Contact:** Open a [GitHub Security Advisory](https://github.com/adein/MeshBot/security/advisories/new) on this repository.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any suggested remediation if you have one

You can expect an acknowledgment within a few days. Please allow reasonable time for a fix before any public disclosure.

## Keeping Your Deployment Secure

- **Never commit `config.yaml`** — it contains API keys and your node's IP address. It is excluded by `.gitignore` by default.
- Store API keys in `config.yaml` only, never hardcode them in source files.
- Restrict network access to your Meshtastic node's TCP port (default 4403) to trusted hosts only.
- Review which modules are enabled and which channels they can post to before deploying.
