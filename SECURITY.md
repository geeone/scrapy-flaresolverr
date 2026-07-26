# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability.

Report security vulnerabilities through GitHub's private vulnerability
reporting feature.

Include a clear description, affected versions, reproduction steps, and the
expected impact.

## Deployment guidance

FlareSolverr should not be exposed directly to the public internet. Bind it to
a private interface or place it behind an authenticated reverse proxy.

Never commit FlareSolverr authentication tokens, proxy credentials, or other
secrets.
