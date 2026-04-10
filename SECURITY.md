# Security Policy

## Supported Versions

As of April 10, 2026:

| Version | Supported          |
| ------- | ------------------ |
| 6.x.x   | :white_check_mark: Current Stable, actively developing |
| 5.x.x   | :hammer_and_wrench: Security updates only |
| < 5.0   | :x: Not supported |

## Supported Python Versions

This library supports Python 3.10 through 3.14. Security fixes will only be tested and released against these versions.

## Reporting a Vulnerability

Please report (suspected) security vulnerabilities to security@healthjoy.com.
You will receive a response from us within 48 hours. If the issue is confirmed,
we will release a patch as soon as possible depending on complexity.

## Scope

The following are considered in scope for security reports:

- Vulnerabilities in the `async-firebase` library code itself
- Issues in how the library handles authentication tokens or credentials
- Misuse of dependencies (`google-auth`, `httpx`) within the library

The following are out of scope:

- Vulnerabilities in Firebase/FCM services themselves (report to Google)
- Issues in third-party dependencies not caused by this library's usage (report upstream)

## Disclosure Policy

We follow coordinated disclosure:

1. Reporter submits the vulnerability to security@healthjoy.com.
2. We acknowledge receipt within 48 hours.
3. We investigate and confirm the issue within 7 days.
4. We develop and release a fix as soon as possible depending on complexity.
5. We publicly disclose the vulnerability after the fix is released.

We kindly ask reporters to give us reasonable time to address the issue before any public disclosure.

## Acknowledgments

We appreciate the efforts of security researchers who help keep this project safe. With the reporter's permission, we will credit them in the release notes for the fix.
