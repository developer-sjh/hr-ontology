# Governance

An ontology that nobody owns drifts. This page says who owns what, how changes are made, and how privacy is handled. The build enforces the parts a program can check.

## Ownership
- Every class and glossary term names a **steward** (a role such as HR Operations, Reward, Organisation Design). The steward is accountable for the definition and approves changes to it.
- The **ontology owner** (a role, not a person) approves structural changes, keeps `VERSION`, and signs off releases.
- The **Data Governance** role owns the temporal pattern, the sensitivity scheme and the access policy.
- Metrics inherit the steward of the glossary term they implement.
The build fails if a class or glossary term has no steward.

## Versioning
One number in `VERSION` applies to every module. Every module's `owl:versionInfo` and `owl:versionIRI` must match it, and the build checks that. The scheme is `MAJOR.MINOR.PATCH`.

| Change | Level | Examples |
|---|---|---|
| **Breaking** | MAJOR | Remove or rename a class, property or vocabulary value that is in use. Change a property's range or cardinality so valid data becomes invalid. Change the meaning of a glossary term or a metric's result for the same data. |
| **Compatible addition** | MINOR | New class, property, vocabulary value, rule, metric or fragment. New optional data. |
| **Fix** | PATCH | Wording of a definition, a corrected typo, a rule bug fix that does not change what valid data looks like. |

A change to a **measure's definition** is breaking even if no file format changes, because reports will change. State it in the changelog and tell consumers.

## Deprecation
Mark a term `owl:deprecated true` and point to its replacement with `dcterms:isReplacedBy`. Keep it for at least one MINOR release before removal in the next MAJOR. Never reuse a retired IRI for a different meaning.

## Making a change
1. Open a change request that states the question the change answers and who the steward is.
2. Update the ontology file, then the rules, the glossary and the measures if they are affected.
3. Add or change tests: a valid case and a bad case for every new rule, and a worked expected value for every new or changed measure.
4. Run `python3 build.py`, `python3 validate.py` and the tests. All must pass.
5. Add a line to `CHANGELOG.md` and set the new `VERSION` in every module.
6. The steward reviews the definition; the ontology owner approves the release.

## Quality gates (automatic)
`build.py` fails the release when:
- a class lacks a label, definition, sensitivity or steward
- a property lacks a label, definition, domain or range, or its range is not a declared class
- a class holding personal data (Confidential or Restricted) has no retention period
- sample data uses a term the ontology does not declare
- a vocabulary value lacks a label or a scheme
- a glossary term lacks a definition, steward or implementing file, or points to a missing file
- a metric names a term not in the glossary, uses an unknown fragment, or a restricted metric is outside `metrics-sensitive/`
- the access policy leaves a sensitivity level unreadable, or allows more than two roles to read Restricted data
- modules disagree on the version

## Privacy by design
- **Minimisation.** The model has no date of birth, address, national ID, health data or protected characteristics. Leave records hold a type, never a medical reason. Adding any of these needs a privacy review first.
- **Sensitivity.** Every class carries one of Public, Internal, Confidential or Restricted. Pay and benefits are Restricted and live in their own files, rules and measures.
- **Access policy as data.** `semantic/access-policy.ttl` lists the kinds of user and the levels they may read. It is a design input for whatever serves the data. Nothing in this project enforces it.
- **Retention.** Personal-data classes carry a retention period (an ISO 8601 duration counted from the end of the employment, or from the end of the process for candidates). A deletion job would read these values. Nothing here deletes anything.
- **Erasure (design).** To erase a person: remove the `Person`, `NameRecord`s and every record that refers to them, in the restricted data first, then the ordinary data. Aggregates that no longer allow identification (counts, rates) may stay. Because every record refers to the person by ID, a query on that ID finds everything to delete. Corrections that `supersede` a deleted record must be deleted with it.
- **Small groups.** A measure grouped by a small unit can identify a person. The people-analyst scope says aggregated data must suppress small groups; suppression itself belongs in the serving layer.

## What is not covered here
Approval workflow tooling, audit logging, and the real enforcement of access and retention. These belong to the system that stores and serves the data.
