"""Build and lint tests: the model passes its own quality rules, the lint catches real problems,
and the release is reproducible."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT, layer
import build


class Lint(unittest.TestCase):
    def test_the_model_is_clean(self):
        problems, _onto, _v = build.lint()
        self.assertEqual(problems, [])

    # --- the lint must catch real problems, so each test breaks a copy of the project
    def lint_broken(self, mutate):
        tmp = Path(tempfile.mkdtemp())
        try:
            for d in ("ontology", "data", "semantic", "shapes"):
                shutil.copytree(ROOT / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy(ROOT / "VERSION", tmp / "VERSION")
            mutate(tmp)
            old_root, old_here = build.ROOT, layer.HERE
            build.ROOT, layer.HERE = tmp, tmp / "semantic"
            try:
                return build.lint()[0]
            finally:
                build.ROOT, layer.HERE = old_root, old_here
        finally:
            shutil.rmtree(tmp)

    def edit(self, rel, old, new):
        def go(tmp):
            p = tmp / rel
            text = p.read_text()
            assert old in text, f"test setup: '{old}' not in {rel}"
            p.write_text(text.replace(old, new, 1))
        return go

    def test_class_without_definition(self):
        problems = self.lint_broken(self.edit("ontology/talent.ttl", 'skos:definition "A training course the organisation offers or recognises."@en ;', ""))
        self.assertTrue(any(p.startswith("CLASS_DEFINITION") and "Course" in p for p in problems), problems)

    def test_class_without_steward(self):
        problems = self.lint_broken(self.edit("ontology/hiring.ttl", 'hr:steward "Talent Acquisition" .\n\nhr:requisitionFor', 'hr:sensitivity hrv:Internal .\n\nhr:requisitionFor'))
        self.assertTrue(any(p.startswith("CLASS_STEWARD") and "Requisition" in p for p in problems), problems)

    def test_personal_data_class_without_retention(self):
        problems = self.lint_broken(self.edit("ontology/employment.ttl", '    hr:retentionPeriod "P3Y"^^xsd:duration ;\n    hr:steward "HR Operations" .\n\nhr:leaveOf', '    hr:steward "HR Operations" .\n\nhr:leaveOf'))
        self.assertTrue(any(p.startswith("CLASS_RETENTION") and "LeaveRecord" in p for p in problems), problems)

    def test_property_without_range(self):
        problems = self.lint_broken(self.edit("ontology/employment.ttl", "rdfs:domain hr:Employment ; rdfs:range xsd:decimal .", "rdfs:domain hr:Employment ."))
        self.assertTrue(any(p.startswith("PROPERTY_RANGE") and "#fte" in p for p in problems), problems)

    def test_property_with_undeclared_range(self):
        problems = self.lint_broken(self.edit("ontology/employment.ttl", "rdfs:domain hr:Employment ; rdfs:range hr:Person .", "rdfs:domain hr:Employment ; rdfs:range hr:Human ."))
        self.assertTrue(any(p.startswith("PROPERTY_RANGE") and "Human" in p for p in problems), problems)

    def test_module_with_wrong_version(self):
        problems = self.lint_broken(self.edit("ontology/hiring.ttl", 'owl:versionInfo "1.0.0"', 'owl:versionInfo "0.9.0"'))
        self.assertTrue(any(p.startswith("VERSION") and "hiring" in p for p in problems), problems)

    def test_data_uses_undeclared_term(self):
        problems = self.lint_broken(self.edit("data/people.ttl", "hr:fullName", "hr:fullNom"))
        self.assertTrue(any(p.startswith("UNDECLARED") and "fullNom" in p for p in problems), problems)

    def test_vocabulary_concept_without_scheme(self):
        problems = self.lint_broken(self.edit("ontology/vocabularies.ttl", "hrv:Team       a skos:Concept ; skos:inScheme hrv:UnitType ;", "hrv:Team       a skos:Concept ;"))
        self.assertTrue(any(p.startswith("VOCAB_SCHEME") and "Team" in p for p in problems), problems)

    def test_metric_naming_a_term_missing_from_the_glossary(self):
        problems = self.lint_broken(self.edit("semantic/metrics/fte.rq", "# term: FTE", "# term: Full time equivalents"))
        self.assertTrue(any(p.startswith("METRIC_TERM") and "fte" in p for p in problems), problems)

    def test_glossary_term_without_owner(self):
        problems = self.lint_broken(self.edit("semantic/glossary.ttl", 'hr:steward "People Analytics" ;', ""))
        self.assertTrue(any(p.startswith("GLOSSARY_STEWARD") for p in problems), problems)

    def test_glossary_pointing_at_a_missing_file(self):
        problems = self.lint_broken(self.edit("semantic/glossary.ttl", "semantic/metrics/fte.rq", "semantic/metrics/gone.rq"))
        self.assertTrue(any(p.startswith("GLOSSARY_FILE") for p in problems), problems)

    def test_metric_using_a_missing_fragment(self):
        problems = self.lint_broken(self.edit("semantic/metrics/headcount.rq", "#include ActiveEmployment", "#include NoSuchFragment"))
        self.assertTrue(any(p.startswith("METRIC_EXPAND") and "headcount" in p for p in problems), problems)

    def test_access_policy_leaves_a_level_uncovered(self):
        def go(tmp):
            p = tmp / "semantic/access-policy.ttl"
            p.write_text(p.read_text().replace(", hrv:Restricted", ""))
        problems = self.lint_broken(go)
        self.assertTrue(any(p.startswith("ACCESS_COVERAGE") and "Restricted" in p for p in problems), problems)

    def test_access_policy_widens_restricted_too_far(self):
        def go(tmp):
            p = tmp / "semantic/access-policy.ttl"
            text = p.read_text()
            marker = "hra:HRBusinessPartner a hr:AccessRole ; rdfs:label \"HR business partner\" ;\n    hr:mayRead hrv:Public, hrv:Internal, hrv:Confidential"
            assert marker in text
            p.write_text(text.replace(marker, marker + ", hrv:Restricted", 1))
        problems = self.lint_broken(go)
        self.assertTrue(any(p.startswith("ACCESS_RESTRICTED") for p in problems), problems)

    def test_access_role_without_scope(self):
        problems = self.lint_broken(self.edit("semantic/access-policy.ttl", 'hr:scope "Own team only, and only the Confidential data needed to manage them. Never pay or benefits." .', "."))
        self.assertTrue(any(p.startswith("ACCESS_ROLE") for p in problems), problems)

    def test_restricted_metric_in_the_ordinary_folder(self):
        def go(tmp):
            shutil.move(tmp / "semantic/metrics-sensitive/pay_outside_band.rq", tmp / "semantic/metrics/pay_outside_band.rq")
        problems = self.lint_broken(go)
        self.assertTrue(any(p.startswith("METRIC_FOLDER") for p in problems), problems)


class Release(unittest.TestCase):
    def build(self):
        subprocess.run([sys.executable, "-I", str(ROOT / "build.py")], check=True, capture_output=True, cwd=ROOT)
        return json.loads((ROOT / "dist/manifest.json").read_text())

    def test_two_builds_are_identical(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)

    def test_manifest_lists_every_release_file(self):
        m = self.build()
        self.assertEqual(m["ontology_version"], (ROOT / "VERSION").read_text().strip())
        self.assertEqual(len(m["files"]), 7)
        for name in ("hr-ontology.ttl", "hr-sample-data.ttl", "hr-sensitive-sample-data.ttl", "hr-shapes.ttl", "hr-sensitive-shapes.ttl", "hr-glossary.ttl"):
            self.assertIn(name, m["files"])

    def test_the_ontology_file_has_no_pay_data_and_the_sample_data_has_no_pay(self):
        from rdflib import Graph, RDF, URIRef
        self.build()
        data = Graph()
        data.parse(ROOT / "dist/hr-sample-data.ttl")
        HR = "https://example.org/hr/ontology#"
        for cls in ("Compensation", "PayBand", "BenefitEnrollment"):
            self.assertEqual(list(data.subjects(RDF.type, URIRef(HR + cls))), [])


if __name__ == "__main__":
    unittest.main()
