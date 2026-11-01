# Changelog

Versioning follows `docs/governance.md`. Every module carries the version in `VERSION`.

## 1.0.0 (2026-10-31)

First release.

- Six ontology modules (core, organisation, employment, talent, hiring, compensation) and controlled vocabularies: 35 classes, 101 properties, 64 coded values.
- Temporal record pattern with valid time and recorded time, and supersession for corrections.
- Stable person IDs, with names as dated records.
- Employment, separation and assignment separate from the position (seat), with reporting lines between positions and the unit structure over time.
- Hiring: requisitions, applications, stage history and offers.
- Skills, credentials, learning, reviews and succession nominations.
- Restricted compensation module: pay bands, pay, benefit plans and enrolments, with separate rules.
- 109 ordinary rules and 21 restricted rules, each named.
- Semantic layer: glossary, 14 measures, 7 shared fragments, access policy.
- Build with lint, validator, and 71 tests.
- Fictional sample data for "Northwind Analytics".
