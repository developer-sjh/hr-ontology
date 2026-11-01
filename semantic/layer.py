#!/usr/bin/env python3
"""The semantic layer: business metrics defined once, run against the graph.

A metric is a SPARQL file in semantic/metrics (or metrics-sensitive for Restricted data).
Shared logic lives in fragments (semantic/fragments/*.rqf), so a concept such as
"current employee" is written in exactly one place and every metric reuses it.

File format
  Metric header (leading comment lines):  "# key: value"
      metric, term (must exist in glossary.ttl), params, description,
      sensitivity (optional), derive (optional, "name = days_between(?a, ?b)")
  Fragment use inside a query:   #include Name key=value key=value
  Parameter inside a fragment:   @{name}     (a private variable: @{_name})

Parameters (as of = valid time, known = what the organisation had recorded):
  asOf, known, periodStart, periodEnd, withinDays
  "known" defaults to the far future, meaning "everything recorded so far".
  "horizon" is computed as asOf + withinDays.

Run from the command line:
  python3 semantic/layer.py dist headcount asOf=2026-10-31
"""
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from rdflib import Graph, Literal

HERE = Path(__file__).parent
PREFIXES = """PREFIX hr: <https://example.org/hr/ontology#>
PREFIX hrv: <https://example.org/hr/vocab#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""
FAR_FUTURE = "9999-12-31"
DATE_PARAMS = {"asOf", "known", "periodStart", "periodEnd", "horizon"}
INCLUDE = re.compile(r"^[ \t]*#include\s+(\w+)((?:\s+\w+=\S+)*)\s*$", re.M)
PLACEHOLDER = re.compile(r"@\{(\w+)\}")


def read_header(text):
    """Leading '# key: value' lines. Returns a dict."""
    meta = {}
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        m = re.match(r"#\s*([\w-]+):\s*(.*)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return meta


def fragments():
    return {p.stem: p.read_text() for p in sorted((HERE / "fragments").glob("*.rqf"))}


def expand(text, frags, counter=None):
    """Replace every '#include' line with the fragment body, recursively."""
    counter = counter if counter is not None else [0]

    def one(m):
        name, argtext = m.group(1), m.group(2)
        if name not in frags:
            raise KeyError(f"unknown fragment '{name}'")
        args = dict(a.split("=", 1) for a in argtext.split())
        counter[0] += 1
        n = counter[0]
        body = "\n".join(l for l in frags[name].splitlines() if not l.startswith("# "))

        def fill(pm):
            key = pm.group(1)
            if key.startswith("_"):
                return f"?_{name}{n}{key}"
            if key not in args:
                raise KeyError(f"fragment '{name}' needs parameter '{key}'")
            return args[key]

        return expand(PLACEHOLDER.sub(fill, body), frags, counter)

    return INCLUDE.sub(one, text)


def literal(name, value):
    return f'"{value}"^^xsd:date' if name in DATE_PARAMS else str(int(value))


def metric_path(name):
    for folder in ("metrics", "metrics-sensitive"):
        p = HERE / folder / f"{name}.rq"
        if p.exists():
            return p
    raise KeyError(f"unknown metric '{name}'")


def list_metrics(sensitive=None):
    """Names of metrics. sensitive=None: all, False: ordinary only, True: restricted only."""
    out = []
    for folder, is_sens in (("metrics", False), ("metrics-sensitive", True)):
        if sensitive is None or sensitive == is_sens:
            out += [p.stem for p in sorted((HERE / folder).glob("*.rq"))]
    return out


def build_query(name, params):
    text = metric_path(name).read_text()
    meta = read_header(text)
    wanted = meta.get("params", "").split()
    values = dict(params)
    values.setdefault("known", FAR_FUTURE)
    for w in wanted:
        if w not in values:
            raise ValueError(f"metric '{name}' needs parameter '{w}'")
    if "withinDays" in values and "asOf" in values:
        values["horizon"] = str(date.fromisoformat(values["asOf"]) + timedelta(days=int(values["withinDays"])))
    body = expand(text, fragments())
    for k, v in sorted(values.items(), key=lambda kv: -len(kv[0])):
        body = re.sub(rf"\?{k}\b", lambda _m, k=k, v=v: literal(k, v), body)
    return PREFIXES + body, meta


def days_between(a, b):
    return (b - a).days


def run(graph, name, **params):
    """Run a metric. Returns a list of dicts (column name -> Python value)."""
    query, meta = build_query(name, params)
    result = graph.query(query)
    cols = [str(v) for v in result.vars]
    rows = []
    for r in result:
        row = {c: (v.toPython() if isinstance(v, Literal) else (str(v) if v is not None else None)) for c, v in zip(cols, r)}
        if "derive" in meta:
            m = re.match(r"(\w+)\s*=\s*days_between\(\?(\w+),\s*\?(\w+)\)", meta["derive"])
            row[m.group(1)] = days_between(row[m.group(2)], row[m.group(3)])
        rows.append(row)
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    folder, metric = Path(sys.argv[1]), sys.argv[2]
    kv = dict(a.split("=", 1) for a in sys.argv[3:])
    g = Graph()
    g.parse(folder / "hr-ontology.ttl")
    g.parse(folder / "hr-sample-data.ttl")
    if metric in list_metrics(True):
        g.parse(folder / "hr-sensitive-sample-data.ttl")
    for row in run(g, metric, **kv):
        print(row)
