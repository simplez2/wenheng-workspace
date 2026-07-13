# Contributing

## Development

1. Create a virtual environment with Python 3.11.
2. Install `package/backend/requirements.txt`.
3. Run backend tests with `PYTHONPATH=package/backend python -m unittest discover -s package/backend/tests -v`.
4. Run `npm ci`, `npm audit`, and `npm run build` in `package/frontend`.

Keep changes scoped. Do not include deployment credentials, databases, generated
documents, build output, or unrelated formatting churn.

## Pull Requests

Describe the root cause, user impact, compatibility considerations, and validation
performed. Security-sensitive reports should follow `SECURITY.md` instead of using
a public pull request.

Contributions are distributed under CC BY-NC-SA 4.0, matching the upstream license.
