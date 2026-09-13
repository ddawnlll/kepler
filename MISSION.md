KEPLER

Objective:
By October 1, 2026, produce the strongest honestly validated portfolio candidate possible, or return NO_DEPLOY.

Current phase:
Smoke-test Qlib + RD-Agent(Q).

Principles:
- Use upstream capabilities before writing code.
- Qlib is the current research engine.
- RD-Agent is optional research automation, not source of truth.
- Smoke-test results are not trading evidence.
- No custom quant framework.
- No LEAN integration during M0.
- No book ingestion during M0.
- No autonomous long-running loop during M0.
- No architecture without an observed blocker.

M0 success:
1. Qlib baseline completes.
2. Qlib metrics/artifacts are produced.
3. RD-Agent completes exactly one controlled quant iteration.
4. The resulting hypothesis, code/experiment, result and feedback are inspectable.
