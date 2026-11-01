"""Shared helpers for the tests: cached graphs and a tiny Turtle builder."""
import sys
from functools import lru_cache
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "semantic"))

import validate  # noqa: E402
import layer  # noqa: E402

PREFIXES = """@prefix hr:  <https://example.org/hr/ontology#> .
@prefix hrv: <https://example.org/hr/vocab#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ent: <https://example.org/hr/id/entity/> .
@prefix loc: <https://example.org/hr/id/location/> .
@prefix unit: <https://example.org/hr/id/unit/> .
@prefix cc:  <https://example.org/hr/id/costcenter/> .
@prefix grd: <https://example.org/hr/id/grade/> .
@prefix job: <https://example.org/hr/id/jobprofile/> .
@prefix sk:  <https://example.org/hr/id/skill/> .
@prefix cert: <https://example.org/hr/id/certification/> .
@prefix p:   <https://example.org/hr/id/person/> .
@prefix nm:  <https://example.org/hr/id/name/> .
@prefix emp: <https://example.org/hr/id/employment/> .
@prefix sep: <https://example.org/hr/id/separation/> .
@prefix asg: <https://example.org/hr/id/assignment/> .
@prefix pos: <https://example.org/hr/id/position/> .
@prefix pd:  <https://example.org/hr/id/position-details/> .
@prefix rl:  <https://example.org/hr/id/reporting-line/> .
@prefix us:  <https://example.org/hr/id/unit-structure/> .
@prefix lv:  <https://example.org/hr/id/leave/> .
@prefix sa:  <https://example.org/hr/id/skill-assertion/> .
@prefix cred: <https://example.org/hr/id/credential/> .
@prefix rev: <https://example.org/hr/id/review/> .
@prefix req: <https://example.org/hr/id/requisition/> .
@prefix app: <https://example.org/hr/id/application/> .
@prefix off: <https://example.org/hr/id/offer/> .
@prefix pay: <https://example.org/hr/id/compensation/> .
@prefix pb:  <https://example.org/hr/id/payband/> .
@prefix plan: <https://example.org/hr/id/benefitplan/> .
@prefix enr: <https://example.org/hr/id/enrollment/> .
@prefix ctry: <https://example.org/hr/id/country/> .
"""


@lru_cache(maxsize=None)
def _graph(*files):
    return validate.load(*files)


def ordinary_graph():
    """A fresh copy of the ordinary data (ontology + vocabularies + reference + people)."""
    g = Graph()
    for t in _graph(*validate.ORDINARY_DATA):
        g.add(t)
    return g


def restricted_graph():
    g = Graph()
    for t in _graph(*validate.RESTRICTED_DATA):
        g.add(t)
    return g


def metrics_graph(sensitive=False):
    g = ordinary_graph()
    if sensitive:
        for t in _graph(*validate.RESTRICTED_DATA):
            g.add(t)
    return g


def add(graph, turtle):
    graph.parse(data=PREFIXES + turtle, format="turtle")
    return graph


def D(s):
    return f'"{s}"^^xsd:date'


def T(iri, cls, props, vf, vt=None, rec="default"):
    """One temporal record as Turtle."""
    parts = [f"a {cls}"] + list(props) + [f"hr:validFrom {D(vf)}"]
    if vt:
        parts.append(f"hr:validTo {D(vt)}")
    if rec == "default":
        rec = vf
    if rec:
        parts.append(f"hr:recordedOn {D(rec)}")
    return f"{iri} " + " ;\n    ".join(parts) + " .\n"


def tags(messages):
    """[(RULE_TAG, focus_tail)] from validate.check() messages."""
    out = []
    for m in messages:
        tag = m.split(":", 1)[0]
        focus = m.rsplit("[", 1)[1].rstrip("]")
        out.append((tag, focus))
    return out
