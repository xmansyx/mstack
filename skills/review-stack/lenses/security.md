# Lens: money, auth and security

Can the change move the wrong amount, reach the wrong tenant's data, or be abused?
Project conventions to read, when the project has them: money and payments, and
auth and scoping.

| Area | Look for |
|---|---|
| Money | Minor units versus decimals, float arithmetic, rounding direction, a currency assumed or hardcoded instead of resolved from the payment gateway or business config, totals that drift between screens |
| Scoping | Every new route and query goes through the row-scoping mechanism; no unscoped `find()` on business data; ids from one business accepted for another |
| Permissions | Each new action checks the same permission its nearest existing sibling checks; client-side hiding is not a permission |
| Input | New endpoints validate body and params; no trusting client-supplied ids, amounts, prices or business ids |
| Secrets and logs | No credentials, tokens, personal data or full request bodies in logs, errors or analytics |
| Security surfaces | Webhook signature checks, uploads and presigned URLs, CSV/XLSX imports, server-side fetches of user-influenced URLs, LLM prompts or output, rate limits: trace the attacker-controlled input on that surface end to end |

For money, the question is always where the rest of the system gets the value:
the canonical failure is a hand-built currency list where the system resolves
currency from the payment provider or account. Cite the existing resolution path.

Every candidate needs a failure scenario: who does what, and what they gain or
what goes wrong. A missing check without a reachable path is not a finding.
