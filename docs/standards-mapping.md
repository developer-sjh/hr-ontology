# Standards mapping

The ontology reuses standard vocabularies by **mapping**, not copying: where a term means the same as a standard term it is declared as a subclass or linked with a SKOS match. Where this model is deliberately different the reason is given.

| This ontology | Standard term | Relation | Note |
|---|---|---|---|
| `hr:Person` | `foaf:Person` | subclass | Declared in the ontology. |
| `hr:Person` | `schema:Person` | `skos:closeMatch` | schema.org has no separate record for names over time. |
| `hr:LegalEntity` | `org:FormalOrganization` | subclass | W3C Organization ontology. |
| `hr:OrganizationalUnit` | `org:OrganizationalUnit` | subclass | Hierarchy is held in `UnitStructure` records, not `org:subOrganizationOf`, so it can be dated. |
| `hr:Position` | `org:Post` | subclass | A seat, as in W3C Org. |
| `hr:Employment` | `org:Membership` | `skos:closeMatch` | W3C Org's membership has a role and period but not type, FTE or separation. |
| `hr:JobProfile` | `schema:Occupation` | `skos:closeMatch` | |
| `hr:Location` | `schema:Place` | `skos:closeMatch` | |
| `hr:Requisition` | `schema:JobPosting` | `skos:closeMatch` | A posting is public advertising; a requisition is the internal approval. |
| `hr:Course` | `schema:Course` | `skos:closeMatch` | |
| `hr:Skill` | `skos:Concept` | subclass | Skills sit in a SKOS scheme with `skos:broader`. |
| All coded values | `skos:Concept` in a `skos:ConceptScheme` | use | |
| `hr:Country` code | ISO 3166-1 alpha-2 | pattern | Checked by `COUNTRY_CODE`. |
| Currency codes | ISO 4217 | pattern | Checked by `COMP_CURRENCY` and `BAND_CURRENCY`. |
| Dates, durations | XML Schema `xsd:date`, `xsd:duration` | use | |

## Skills taxonomy (ESCO, O*NET)
The sample skill scheme (`data/reference.ttl`) is deliberately small and local. To align it, add one `skos:closeMatch` or `skos:exactMatch` from each local skill to the matching ESCO skill URI or O*NET element, taken from the official downloads. No ESCO or O*NET identifiers are filled in because inventing them would be wrong. The structure is ready: skills are `skos:Concept`s, so mappings need no schema change.

## HR Open Standards
HR Open Standards is an interchange format for exchanging records between systems, not an ontology. When a real integration is built, map its fields to this ontology in the source mapping layer; do not copy its field names into the model.

## Where this model differs on purpose
- **Time is explicit.** Standards vocabularies mostly model the current state. Here every changing fact carries valid and recorded dates.
- **Names are records.** schema.org and FOAF give a person a single name property.
- **Position is a seat.** Reporting is between positions, not between people.
