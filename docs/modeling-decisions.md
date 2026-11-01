# Modelling decisions

Each decision says what was chosen, why, and what was rejected. Read this before changing the model.

## 1. People are identified by an ID, names are records
**Chosen:** `Person` has an immutable `personId` (P and six digits), and the IRI is built from it. Names are dated `NameRecord`s of a type (legal or preferred).
**Why:** names repeat (the sample has two "Daniel Kim"s) and change. If identity came from a name, every reference would break on a marriage or a correction.
**Rejected:** a name property on Person (cannot hold history, invites joins on names); using an email or a payroll number as the ID (they change and are personal data).
**Consequence:** every output that shows a name must show the ID beside it. The measures do.

## 2. Employment, Assignment and Position are separate
**Chosen:** `Employment` is the period someone worked for a legal entity, with type and FTE. `Assignment` puts an employment into a `Position` for a period and must lie inside the employment. `Position` is a seat with its own identity and history (`PositionDetails`).
**Why:** each answers a different question (are they with us, what do they do, does the seat exist). Putting them together makes vacancies, leavers and reorganisations impossible to express.
**Rejected:** a single "assignment" record carrying everything (the prototype this replaced); modelling the person as holding the position directly (loses vacancies).

## 3. Leaving is a Separation, and the category comes from the reason
**Chosen:** the last day is the employment's `validTo`. A `Separation` holds the reason, a leaf concept in a two-level scheme whose parent is the category (voluntary, involuntary, other).
**Why:** the last day is stored once. The category is never stored, so reason and category cannot disagree.
**Rejected:** storing `exitCategory` beside `terminationReason` (two fields that can contradict).

## 4. Rehire is a new employment, linked back
**Chosen:** a rehire is a later `Employment` with `previousEmployment`. A person has only one open employment per employer.
**Why:** terms, FTE and reason for leaving differ between spells. Tenure restarts (see the glossary) but earlier service stays visible.
**Rejected:** reopening the old employment (loses the gap and the reason).

## 5. Two kinds of time
**Chosen:** every changing fact is a `TemporalRecord` with `validFrom`/`validTo` (inclusive; no end means current) and `recordedOn`. A correction is a new record that `supersedes` the old one.
**Why:** "when was it true" and "when did we know" differ whenever there is a backdated change or a correction, which in HR is routine. Without both, a report cannot be reproduced.
**Rejected:** overwriting values (loses history); a single date (cannot answer "what did we report in March").
**Cost:** queries must say how they treat superseded records. The shared `ValidRecord` fragment does this once.

## 6. Reporting follows seats
**Chosen:** `ReportingLine` connects positions, with a type (solid or dotted) and dates. A person's manager is whoever holds the supervisor position.
**Why:** managers leave and seats stay vacant, but the structure should not change. Matrix reporting is just a second, dotted line.
**Rejected:** a `reportsTo` property from person to person (breaks on vacancy, cannot be dated cleanly).

## 7. Coded values are SKOS concepts, not strings
**Chosen:** employment type, separation reason, proficiency and the rest are concepts in named schemes, checked by the rules.
**Why:** values can be added, retired, mapped to other standards and given definitions without touching the ontology.
**Rejected:** string enumerations in the schema (every change would be a breaking change); OWL enumerations (cannot carry definitions or hierarchy).

## 8. Pay is a separate module with separate rules
**Chosen:** compensation, pay bands and benefits are in their own ontology file, data file and rule file, and all carry the Restricted level. Pay refers to an employment by IRI and holds no personal details. A pay record requires a grade.
**Why:** access and retention differ, and the safest sensitive data is the data that is not mixed in. The ordinary rules do not mention pay, so validating ordinary data never touches it.
**Rejected:** pay properties on Employee (cannot be separated later); validating pay without employment dates (cannot check that pay lies inside the employment, so the employment records are loaded as read-only context).

## 9. Skills and credentials are records, not properties
**Chosen:** `SkillAssertion` says a person has a skill at a level from a source, for a period. A credential is the award of a certification, valid until it expires, and a renewal follows the old one.
**Why:** growth, loss and evidence quality are all HR questions. A flat "person has skill" cannot answer any of them.

## 10. Definitions live in one place
**Chosen:** shared logic is in fragments. A measure includes a fragment instead of restating it, and a test fails if a measure copies the validity or correction rules. Every measure names a glossary term.
**Why:** if "current employee" is written in several queries, they drift apart and two reports disagree.
**Rejected:** a plain list of SPARQL files (the original prototype). Also rejected, for now: a full metrics engine or a virtualised layer over a real database, which belongs with source integration.

## 11. Rules are honest about their limits
**Chosen:** the manager and unit loop rules check up to four levels, and each branch repeats the focus-node pattern because a SPARQL `FILTER` inside a `UNION` branch cannot see variables bound outside it. Both facts are written where the rule is.
**Why:** a rule that silently does less than it claims is worse than no rule.

## 12. Things deliberately left out
Time tracking, leave accrual, public holidays, compliance cases, goals and OKRs, interview feedback, diversity data, calibration, and a real source mapping. Each is listed in the README. Diversity and disciplinary data in particular need their own privacy design before they are modelled.
