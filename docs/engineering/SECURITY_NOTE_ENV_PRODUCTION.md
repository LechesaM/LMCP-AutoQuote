# Security Note — `.env.production`

The current public release branch tracks `.env.production`. The visible values appear placeholder/default-like, but this must not be interpreted as proof that no credential exposure occurred historically.

SEC-006 must:

1. inspect repository history for secrets and credential reuse;
2. identify whether any tracked value was ever live;
3. rotate any credential that was live or reused;
4. decide whether `.env.production` should be removed from tracking in favour of safe examples plus external secret injection;
5. add preventative scanning/controls where practical.

Do not publish real replacement secrets to GitHub during remediation.
