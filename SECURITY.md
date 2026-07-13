# Security Policy

## Supported Version

Security fixes are applied to the latest `main` branch. Older deployments should
upgrade before reporting an issue that has already been fixed on `main`.

## Reporting

Do not open a public issue for a vulnerability or include production credentials
in an issue, discussion, log, or screenshot. Use GitHub private vulnerability
reporting for this repository.

Include the affected endpoint or component, reproduction steps, impact, and a
minimal proof of concept with all credentials removed.

## Deployment Requirements

- Set `ENVIRONMENT=production`.
- Use a random `SECRET_KEY` with at least 32 characters.
- Set a strong `ADMIN_PASSWORD` or bcrypt `ADMIN_PASSWORD_HASH`.
- Restrict `CORS_ORIGINS` to the deployed frontend origins.
- Keep `ALLOW_USER_AI_CONFIG=false` unless user-supplied providers are required.
- Keep `ALLOW_PRIVATE_AI_ENDPOINTS=false` for internet-facing deployments.
- Bind the application port to loopback and terminate TLS at a reverse proxy.
- Never commit `.env`, `app.env`, databases, uploaded documents, or API keys.

The application refuses to start in production when administrator credentials or
the JWT signing key are missing or use known placeholder values.
