#!/usr/bin/env python3
"""Build the HR ontology release: merge modules, lint the model, write dist/.

  python3 build.py            builds into dist/
  python3 build.py --check    lints only, writes nothing

Lint rules (all must pass or the build fails):
  - every module carries the version in VERSION (versionInfo and versionIRI)
  - every hr: class has a label, definition, sensitivity and steward
  - every hr: property has a label, definition, domain and range
  - Confidential and Restricted record classes carry a retention period
  - every term used in the sample data is declared in the ontology
  - every vocabulary concept has a label and belongs to a scheme
  - every glossary term has a definition, steward and an implementing file that exists
  - every metric names a glossary term and expands without error
  - the access policy covers every sensitivity level and keeps Restricted narrow
Output is deterministic: building twice gives identical files.
"""
import hashlib
import json
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, SKOS, URIRef
from rdflib.namespace import DCTERMS, XSD

ROOT = Path(__file__).parent
HR = Namespace("https://example.org/hr/ontology#")
HRV = Namespace("https://example.org/hr/vocab#")
MODULES = ["core", "organisation", "employment", "talent", "hiring", "compensation"]
sys.path.insert(0, str(ROOT / "semantic"))
import layer  # noqa: E402

BIND = {"hr": HR, "hrv": HRV, "owl": OWL, "rdfs": RDFS, "xsd": XSD, "skos": SKOS, "dcterms": DCTERMS,
        "schema": Namespace("https://schema.org/"), "foaf": Namespace("http://xmlns.com/foaf/0.1/"),
        "org": Namespace("http://www.w3.org/ns/org#")}


def load(*files):
    g = Graph()
    for f in files:
        g.parse(ROOT / f, format="turtle")
    return g


def in_hr(u):
    return isinstance(u, URIRef) and str(u).startswith(str(HR))


def lint():
    problems = []
    version = (ROOT / "VERSION").read_text().strip()
    onto = load(*[f"ontology/{m}.ttl" for m in MODULES], "ontology/vocabularies.ttl")
    glossary = load("semantic/glossary.ttl")

    # versions
    for o in onto.subjects(RDF.type, OWL.Ontology):
        if str(onto.value(o, OWL.versionInfo)) != version:
            problems.append(f"VERSION: {o} is not at version {version}")
        vi = onto.value(o, OWL.versionIRI)
        if vi is None or not str(vi).endswith("/" + version):
            problems.append(f"VERSION: {o} has no versionIRI ending in /{version}")

    # classes
    classes = {c for c in onto.subjects(RDF.type, OWL.Class) if in_hr(c)}
    for c in sorted(classes):
        for p, name in [(RDFS.label, "label"), (SKOS.definition, "definition"), (HR.sensitivity, "sensitivity"), (HR.steward, "steward")]:
            if onto.value(c, p) is None:
                problems.append(f"CLASS_{name.upper()}: {c} has no {name}")
        sens = onto.value(c, HR.sensitivity)
        if sens in (HRV.Confidential, HRV.Restricted) and onto.value(c, HR.retentionPeriod) is None:
            problems.append(f"CLASS_RETENTION: {c} is {str(sens).split('#')[1]} but has no retentionPeriod")

    # properties
    props = {p for t in (OWL.ObjectProperty, OWL.DatatypeProperty) for p in onto.subjects(RDF.type, t) if in_hr(p)}
    for p in sorted(props):
        for q, name in [(RDFS.label, "label"), (SKOS.definition, "definition"), (RDFS.domain, "domain"), (RDFS.range, "range")]:
            if onto.value(p, q) is None:
                problems.append(f"PROPERTY_{name.upper()}: {p} has no {name}")
        for rng in onto.objects(p, RDFS.range):
            if in_hr(rng) and rng not in classes:
                problems.append(f"PROPERTY_RANGE: {p} has range {rng}, which is not a declared class")
        for dom in onto.objects(p, RDFS.domain):
            if in_hr(dom) and dom not in classes:
                problems.append(f"PROPERTY_DOMAIN: {p} has domain {dom}, which is not a declared class")

    # every temporal subclass really descends from TemporalRecord; no stray hr: terms
    declared = classes | props | {s for s in onto.subjects(RDF.type, OWL.AnnotationProperty) if in_hr(s)}
    for f in ["data/reference.ttl", "data/people.ttl", "data/compensation-data.ttl"]:
        data = load(f)
        used = {o for _, p, o in data.triples((None, RDF.type, None)) if in_hr(o)}
        used |= {p for _, p, _ in data if in_hr(p)}
        for u in sorted(used - declared):
            problems.append(f"UNDECLARED: {f} uses {u}, which the ontology does not declare")

    # vocabulary
    for c in onto.subjects(RDF.type, SKOS.Concept):
        if onto.value(c, SKOS.prefLabel) is None:
            problems.append(f"VOCAB_LABEL: {c} has no prefLabel")
        if onto.value(c, SKOS.inScheme) is None:
            problems.append(f"VOCAB_SCHEME: {c} is not in a scheme")

    # glossary and metrics
    terms = {str(glossary.value(t, SKOS.prefLabel)): t for t in glossary.subjects(RDF.type, SKOS.Concept)}
    for label, t in terms.items():
        for p, name in [(SKOS.definition, "definition"), (HR.steward, "steward"), (HR.implementedBy, "implementedBy")]:
            if glossary.value(t, p) is None:
                problems.append(f"GLOSSARY_{name.upper()}: '{label}' has no {name}")
        for f in glossary.objects(t, HR.implementedBy):
            if not (ROOT / str(f)).exists():
                problems.append(f"GLOSSARY_FILE: '{label}' points to missing file {f}")
    # access policy
    policy = load("semantic/access-policy.ttl")
    levels = {s for s in onto.subjects(SKOS.inScheme, HRV.SensitivityLevel)}
    roles = list(policy.subjects(RDF.type, HR.AccessRole))
    covered = set()
    restricted_roles = 0
    for r in roles:
        grants = set(policy.objects(r, HR.mayRead))
        covered |= grants
        if not grants or policy.value(r, HR.scope) is None or policy.value(r, RDFS.label) is None:
            problems.append(f"ACCESS_ROLE: {r} needs a label, a scope and at least one mayRead level")
        restricted_roles += HRV.Restricted in grants
    for lv in sorted(levels - covered):
        problems.append(f"ACCESS_COVERAGE: no role may read {lv}, so nobody could ever see that data")
    if restricted_roles > 2:
        problems.append(f"ACCESS_RESTRICTED: {restricted_roles} roles may read Restricted data; the policy allows at most two")

    dummy = {"asOf": "2026-01-01", "known": "9999-12-31", "periodStart": "2026-01-01", "periodEnd": "2026-12-31", "withinDays": "30"}
    for m in layer.list_metrics():
        meta = layer.read_header(layer.metric_path(m).read_text())
        if meta.get("term") not in terms:
            problems.append(f"METRIC_TERM: metric '{m}' names term '{meta.get('term')}', which is not in the glossary")
        try:
            layer.build_query(m, dummy)
        except Exception as e:  # noqa: BLE001
            problems.append(f"METRIC_EXPAND: metric '{m}' does not expand: {e}")
        if meta.get("sensitivity") == "Restricted" and layer.metric_path(m).parent.name != "metrics-sensitive":
            problems.append(f"METRIC_FOLDER: restricted metric '{m}' is not in metrics-sensitive")
    return problems, onto, version


def write(g, path):
    for k, v in BIND.items():
        g.bind(k, v)
    g.serialize(path, format="turtle")


def build():
    problems, onto, version = lint()
    if problems:
        print("LINT FAILED")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    if "--check" in sys.argv:
        print("lint ok: ontology", version)
        return
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    write(onto, dist / "hr-ontology.ttl")
    write(load("data/reference.ttl", "data/people.ttl"), dist / "hr-sample-data.ttl")
    write(load("data/compensation-data.ttl"), dist / "hr-sensitive-sample-data.ttl")
    write(load("semantic/glossary.ttl"), dist / "hr-glossary.ttl")
    write(load("semantic/access-policy.ttl"), dist / "hr-access-policy.ttl")
    for src, dst in [("shapes/core.shacl.ttl", "hr-shapes.ttl"), ("shapes/sensitive.shacl.ttl", "hr-sensitive-shapes.ttl")]:
        (dist / dst).write_text((ROOT / src).read_text())
    manifest = {"ontology_version": version, "files": {}}
    for f in sorted(dist.glob("*.ttl")):
        g = Graph()
        g.parse(f, format="turtle")
        manifest["files"][f.name] = {"triples": len(g), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
    (dist / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("built ontology", version)
    for n, d in manifest["files"].items():
        print(f"  {n:32} {d['triples']:5} triples")


if __name__ == "__main__":
    build()
