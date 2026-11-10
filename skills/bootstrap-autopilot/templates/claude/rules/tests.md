---
paths: {{TEST_GLOBS}}
---

# Test conventions

- Keep tests deterministic. Inject the clock, use fake timers, seed any randomness. Never sleep or wait on real time.
- Never touch a real external service or a real key. Each service sits behind one module; tests use its fake.
- Each test proves one behaviour from a "Done when" bullet or a spec rule. Name it after that behaviour.
- A test must fail if the behaviour breaks. Assert on the outcome, not on the fact that a function was called.
- Never weaken, skip or delete a test to get green. A test that is wrong gets fixed and the fix is explained in the PROGRESS entry.
- Fake keys must not look like real ones: the push guard refuses any commit holding a string shaped like a real key (`sk-ant-…`, `sk-…`, `ghp_…`, `AKIA…`, `AIza…`, a PEM header), fake or not. Use an obvious placeholder (`'test-anthropic-key'`), or build a shape-checked fake at runtime (`'sk-ant-' + 'x'.repeat(40)`).
