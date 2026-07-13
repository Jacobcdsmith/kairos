## What does this change?

<!-- One or two sentences: what behavior changes, and why. -->

## Checklist

- [ ] `ruff format --check src tests` passes
- [ ] `ruff check src tests` passes
- [ ] `pyright` passes with zero errors
- [ ] `pytest` passes, and I added/updated tests for the behavior change
- [ ] I did not add a dependency on model inference, remote services, or anything in the
      [non-goals list](../docs/architecture.md#non-goals-v01)
- [ ] I updated `docs/cli.md` and/or `docs/architecture.md` if this changes command behavior, schema, or provenance guarantees

## How was this tested?

<!-- Commands you ran, or which existing/new tests cover this. -->
