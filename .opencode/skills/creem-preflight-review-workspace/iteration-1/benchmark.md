# Skill Benchmark: creem-preflight-review

**Model**: openai/gpt-5.5
**Date**: 2026-05-18
**Evals**: 0, 1, 2 (1 run each per configuration)

## Summary

| Metric | With Skill | Without Skill | Delta |
|--------|------------|---------------|-------|
| Pass Rate | 100% ± 0% | 100% ± 0% | +0.00 |
| Time | 0.0s ± 0.0s | 0.0s ± 0.0s | +0.0s |
| Tokens | 0 ± 0 | 0 ± 0 | +0 |

## Analyst Notes

- All current assertions pass for both configurations, so they are useful as minimum completeness checks but weak as differentiators.
- With-skill outputs are more consistently formatted around Creem account-review risk, official requirements, stay-in-test-mode language, and manual confirmation items.
- Baseline outputs were also strong because the prompts were specific and the repo contains relevant context.
- Next iteration should add stricter assertions for exact report template, risk scale labels, official Creem citations, and re-review wording discipline.
