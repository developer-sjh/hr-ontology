#!/usr/bin/env python3
"""Validate the sample data against the SHACL rules. Two separate checks.

  1. Ordinary data   shapes/core.shacl.ttl       data: ontology + vocabularies + reference + people
  2. Restricted data shapes/sensitive.shacl.ttl  data: pay and benefits, with the ordinary data loaded
                                                 only as read-only context (employment dates)

The ordinary check never sees pay or benefits. Warnings are shown but do not fail the check.
Run:  python3 validate.py          (needs rdflib and pyshacl)
Exit code 0 when both checks have no violations, 1 otherwise.
"""
import re
import sys
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace, RDF
from rdflib.namespace import SH

ROOT = Path(__file__).parent


def load(*files):
    g = Graph()
    for f in files:
        g.parse(ROOT / f, format="turtle")
    return g


ONTOLOGY = [f"ontology/{m}.ttl" for m in ["core", "organisation", "employment", "talent", "hiring", "compensation"]] + ["ontology/vocabularies.ttl"]
ORDINARY_DATA = ONTOLOGY + ["data/reference.ttl", "data/people.ttl"]
RESTRICTED_DATA = ["data/compensation-data.ttl"]


def check(data_graph, shapes_graph):
    """Returns (violations, warnings): two lists of message strings."""
    conforms, results, _ = validate(data_graph, shacl_graph=shapes_graph, inference="none", advanced=True,
                                    allow_warnings=True, meta_shacl=False, debug=False)
    violations, warnings = [], []
    all_results = list(results.subjects(RDF.type, SH.ValidationResult))
    reported_values = {results.value(r, SH.value) for r in all_results}
    for r in all_results:
        msg = str(results.value(r, SH.resultMessage))
        focus = results.value(r, SH.focusNode)
        if not re.match(r"^[A-Z][A-Z0-9_]+:", msg) and focus in reported_values:
            continue  # the nested detail of a scheme check; its tagged parent result is already reported
        text = f"{msg} [{str(focus).rsplit('/', 1)[-1]}]"
        (warnings if results.value(r, SH.resultSeverity) == SH.Warning else violations).append(text)
    return sorted(violations), sorted(warnings)


def ordinary(data=None):
    return check(data if data is not None else load(*ORDINARY_DATA), load("shapes/core.shacl.ttl"))


def restricted(data=None, context=None):
    """Pay data validated alone; the ordinary data is added only as context."""
    g = Graph()
    for src in (data if data is not None else load(*RESTRICTED_DATA), context if context is not None else load(*ORDINARY_DATA)):
        for t in src:
            g.add(t)
    return check(g, load("shapes/sensitive.shacl.ttl"))


def main():
    ok = True
    for name, fn in [("Ordinary data", ordinary), ("Restricted data (pay and benefits)", restricted)]:
        violations, warnings = fn()
        print(("PASS " if not violations else "FAIL ") + name)
        for v in violations:
            print("   violation:", v)
        for w in warnings:
            print("   warning:  ", w)
        ok &= not violations
    print("ALL RULES HOLD" if ok else "VIOLATIONS FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
