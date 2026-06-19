---
name: Spec drift (WxO import spec changed)
about: Report that the watsonx Orchestrate import spec has changed and no longer matches what langgraph-wxo generates/validates
title: "[spec-drift] "
labels: spec-drift
assignees: ''
---

## What changed in the WxO import spec?

Describe the change in the watsonx Orchestrate native import specification
(new field, renamed field, removed field, changed validation rule, etc.).

## Source / evidence

Where did you observe this change? Link the IBM documentation, release notes,
or paste the relevant excerpt.

- Spec / doc URL:
- WxO version or date observed:

## Affected area

Which part of langgraph-wxo is impacted?

- [ ] Generated import spec (template output)
- [ ] Validator rule(s)
- [ ] Emulator behavior
- [ ] CLI command(s)
- [ ] Other:

## Current behavior

What does langgraph-wxo currently produce/validate?

```yaml
<current spec or validator output>
```

## Expected behavior (per new spec)

What should it produce/validate now?

```yaml
<expected spec>
```

## Suggested fix

If known, point to the template, validator rule, or emulator code that needs
updating.

## Additional context

Anything else relevant (backwards-compat concerns, version gating, etc.).
