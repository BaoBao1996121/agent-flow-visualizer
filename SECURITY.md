# Security policy

## Supported versions

Agent Anthill is pre-1.0. Security fixes are applied to the latest main branch and the most recent tagged release when practical.

## Reporting a vulnerability

Please use the repository's private GitHub Security Advisory form after the project is published. Do not open a public issue for vulnerabilities involving code execution, secret disclosure, path access, cross-site scripting, trace content, or replay side effects.

Include:

- affected commit/version;
- reproducible steps with synthetic data;
- impact and required attacker access;
- any proposed mitigation;
- whether disclosure is time-sensitive.

Maintainers should acknowledge a complete report within seven days and coordinate remediation/disclosure based on severity.

## Important current limitation

The Python runtime tracer imports and executes selected project code in the server process. Use it only with trusted local code and without administrator/root privileges. See [the security model](docs/SECURITY_AND_PRIVACY.md).
