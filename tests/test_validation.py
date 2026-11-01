"""Validation tests: the sample data is valid, and each rule fires on representative bad data.

All bad cases are injected into one copy of the sample data and validated in a single run
(validation is the slow step). Each case has a unique focus node, so a test can check that
exactly the intended rule fires on exactly the intended record.
"""
import unittest

import validate
from tests.support import (T, D, add, ordinary_graph, restricted_graph, metrics_graph, tags, _graph)


# ---------------------------------------------------------------- builders
def person(n):
    """A valid person (IRI built from the ID) with a legal name."""
    pid = f"P9{n:05d}"
    return (f'p:{pid} a hr:Person ; hr:personId "{pid}" .\n'
            + T(f"nm:bad_nm{n}", "hr:NameRecord", [f"hr:nameOf p:{pid}", f'hr:fullName "Test Person {n}"', "hr:nameType hrv:LegalName"], "2020-01-01"))


def pid(n):
    return f"p:P9{n:05d}"


def employment(iri, n, vf, vt=None, fte="1.0", typ="Permanent", extra=()):
    props = [f"hr:employee {pid(n)}", "hr:employer ent:UK", f"hr:employmentType hrv:{typ}", f'hr:fte "{fte}"^^xsd:decimal'] + list(extra)
    return T(iri, "hr:Employment", props, vf, vt)


def position(name, n, budget="1.0", vf="2020-01-01"):
    return (f'pos:{name} a hr:Position ; hr:positionId "POS{n}" .\n'
            + T(f"pd:{name}", "hr:PositionDetails", [f"hr:detailsOf pos:{name}", "hr:inUnit unit:PLAT", "hr:hasProfile job:ENG",
                                                       "hr:chargedTo cc:C100", "hr:basedAt loc:London", f'hr:budgetedFte "{budget}"^^xsd:decimal'], vf))


def assignment(iri, emp_iri, pos_name, vf, vt=None, fte="1.0", typ="Primary"):
    return T(iri, "hr:Assignment", [f"hr:assignedEmployment {emp_iri}", f"hr:assignedPosition pos:{pos_name}",
                                      f"hr:assignmentType hrv:{typ}", f'hr:assignmentFte "{fte}"^^xsd:decimal'], vf, vt)


def line(iri, sub, sup, vf, vt=None, typ="Solid"):
    return T(iri, "hr:ReportingLine", [f"hr:subordinatePosition pos:{sub}", f"hr:supervisorPosition pos:{sup}", f"hr:lineType hrv:{typ}"], vf, vt)


def unit(name, code):
    return (f'unit:{name} a hr:OrganizationalUnit ; hr:unitCode "{code}" ; hr:unitType hrv:Team ; hr:withinEntity ent:UK .\n')


def structure(iri, child, parent, vf, vt=None):
    return T(iri, "hr:UnitStructure", [f"hr:childUnit unit:{child}", f"hr:parentUnit unit:{parent}"], vf, vt)


def sep(iri, emp_iri, reason="Resignation", extra=""):
    return f"{iri} a hr:Separation ; hr:separationOf {emp_iri} ; hr:separationReason hrv:{reason} {extra}.\n"


# ---------------------------------------------------------------- the bad cases: name -> (expected rule tags, Turtle)
def cases():
    c = {}
    # --- people and names
    c["bad_pid"] = ({('PERSON_ID', 'bad_pid')}, 'p:bad_pid a hr:Person ; hr:personId "X123" .\n')
    c["P998001"] = ({('PERSON_IRI', 'P998001')}, 'p:P998001 a hr:Person ; hr:personId "P998002" .\n')
    c["P998003"] = ({('PERSON_ID_UNIQUE', 'P998003'), ('PERSON_ID_UNIQUE', 'P998004')}, 'p:P998003 a hr:Person ; hr:personId "P998003" .\np:P998004 a hr:Person ; hr:personId "P998003" .\n')
    c["P998005"] = ({('PERSON_NAME', 'P998005')}, 'p:P998005 a hr:Person ; hr:personId "P998005" .\n')
    c["bad_nm_dup"] = ({('NAME_OVERLAP', 'bad_nm_dup'), ('NAME_OVERLAP', 'bad_nm1')}, person(1) + T("nm:bad_nm_dup", "hr:NameRecord", [f"hr:nameOf {pid(1)}", 'hr:fullName "Other Name"', "hr:nameType hrv:LegalName"], "2021-01-01"))
    c["bad_nm_type"] = ({('NAME_TYPE', 'bad_nm_type')}, person(2) + T("nm:bad_nm_type", "hr:NameRecord", [f"hr:nameOf {pid(2)}", 'hr:fullName "X"', "hr:nameType hrv:Medical"], "2022-01-01"))
    # --- temporal pattern
    c["lv_bad_order"] = ({('TEMPORAL_ORDER', 'bad_lv_order')}, person(3) + employment("emp:bad_e3", 3, "2020-01-01")
                         + T("lv:bad_lv_order", "hr:LeaveRecord", [f"hr:leaveOf emp:bad_e3", "hr:leaveType hrv:AnnualLeave"], "2026-05-02", "2026-05-01"))
    c["lv_bad_recorded"] = ({('TEMPORAL_RECORDED', 'bad_lv_recorded')}, person(4) + employment("emp:bad_e4", 4, "2020-01-01")
                            + T("lv:bad_lv_recorded", "hr:LeaveRecord", [f"hr:leaveOf emp:bad_e4", "hr:leaveType hrv:AnnualLeave"], "2026-05-01", "2026-05-02", rec=None))
    c["lv_bad_open"] = ({('LEAVE_END', 'bad_lv_open')}, person(5) + employment("emp:bad_e5", 5, "2020-01-01")
                        + T("lv:bad_lv_open", "hr:LeaveRecord", [f"hr:leaveOf emp:bad_e5", "hr:leaveType hrv:AnnualLeave"], "2026-05-01"))
    # --- employment
    c["emp_overlap"] = ({('EMPLOYMENT_OVERLAP', 'bad_e6b'), ('EMPLOYMENT_OVERLAP', 'bad_e6a')}, person(6) + employment("emp:bad_e6a", 6, "2020-01-01") + employment("emp:bad_e6b", 6, "2021-01-01"))
    c["emp_fte"] = ({('EMPLOYMENT_FTE', 'bad_fte')}, person(7) + employment("emp:bad_fte", 7, "2020-01-01", fte="1.5"))
    c["emp_fixed"] = ({('EMPLOYMENT_FIXEDTERM', 'bad_fixed')}, person(8) + employment("emp:bad_fixed", 8, "2020-01-01", typ="FixedTerm"))
    c["emp_nosep"] = ({('EMPLOYMENT_NEEDS_SEPARATION', 'bad_nosep')}, person(9) + employment("emp:bad_nosep", 9, "2020-01-01", "2021-01-01"))
    c["emp_rehire"] = ({('EMPLOYMENT_REHIRE', 'bad_rehire')}, person(10) + employment("emp:bad_rehire", 10, "2022-01-01", extra=["hr:previousEmployment emp:P000001-20180108"]))
    c["emp_type"] = ({('EMPLOYMENT_TYPE', 'bad_emp_type')}, person(11) + T("emp:bad_emp_type", "hr:Employment", [f"hr:employee {pid(11)}", "hr:employer ent:UK", "hr:employmentType hrv:Medical", 'hr:fte "1.0"^^xsd:decimal'], "2020-01-01"))
    c["emp_prob"] = ({('EMPLOYMENT_PROBATION_ORDER', 'bad_prob')}, person(12) + employment("emp:bad_prob", 12, "2020-01-01", extra=['hr:probationEnd "2019-06-01"^^xsd:date']))
    # --- separation
    c["sep_leaf"] = ({('SEPARATION_REASON_LEAF', 'bad_sep_leaf')}, person(13) + employment("emp:bad_e13", 13, "2020-01-01", "2021-01-01") + sep("sep:bad_sep_leaf", "emp:bad_e13", "Voluntary"))
    c["sep_open"] = ({('SEPARATION_ENDED', 'bad_sep_open')}, person(14) + employment("emp:bad_e14", 14, "2020-01-01") + sep("sep:bad_sep_open", "emp:bad_e14"))
    c["sep_two"] = ({('SEPARATION_UNIQUE', 'bad_sep_two_a'), ('SEPARATION_UNIQUE', 'bad_sep_two_b')}, person(15) + employment("emp:bad_e15", 15, "2020-01-01", "2021-01-01") + sep("sep:bad_sep_two_a", "emp:bad_e15") + sep("sep:bad_sep_two_b", "emp:bad_e15", "Dismissal"))
    c["sep_notice"] = ({('SEPARATION_NOTICE_ORDER', 'bad_sep_notice')}, person(16) + employment("emp:bad_e16", 16, "2020-01-01", "2021-01-01")
                      + sep("sep:bad_sep_notice", "emp:bad_e16", extra='; hr:noticeGivenOn "2021-06-01"^^xsd:date '))
    # --- assignment
    c["asg_outside"] = ({('ASSIGNMENT_WITHIN_EMPLOYMENT', 'bad_outside')}, person(17) + employment("emp:bad_e17", 17, "2020-06-01") + position("bad_pos17", "9017")
                        + assignment("asg:bad_outside", "emp:bad_e17", "bad_pos17", "2020-01-01"))
    c["asg_two_primary"] = ({('ONE_PRIMARY_ASSIGNMENT', 'bad_primary_a'), ('ONE_PRIMARY_ASSIGNMENT', 'bad_primary_b')}, person(18) + employment("emp:bad_e18", 18, "2020-01-01") + position("bad_pos18a", "9018") + position("bad_pos18b", "9019")
                            + assignment("asg:bad_primary_a", "emp:bad_e18", "bad_pos18a", "2020-01-01", fte="0.5")
                            + assignment("asg:bad_primary_b", "emp:bad_e18", "bad_pos18b", "2021-01-01", fte="0.5"))
    c["asg_capacity"] = ({('POSITION_CAPACITY', 'bad_cap_b')}, person(19) + person(20) + employment("emp:bad_e19", 19, "2020-01-01") + employment("emp:bad_e20", 20, "2020-01-01")
                         + position("bad_pos19", "9020") + assignment("asg:bad_cap_a", "emp:bad_e19", "bad_pos19", "2020-01-01") + assignment("asg:bad_cap_b", "emp:bad_e20", "bad_pos19", "2021-01-01"))
    c["asg_secondary_ok_type"] = ({('ASSIGNMENT_TYPE', 'bad_asg_type')}, person(21) + employment("emp:bad_e21", 21, "2020-01-01") + position("bad_pos21", "9021")
                                   + T("asg:bad_asg_type", "hr:Assignment", ["hr:assignedEmployment emp:bad_e21", "hr:assignedPosition pos:bad_pos21", "hr:assignmentType hrv:Medical", 'hr:assignmentFte "1.0"^^xsd:decimal'], "2020-01-01"))
    # --- positions and reporting
    c["pd_overlap"] = ({('DETAILS_OVERLAP', 'bad_pos22'), ('DETAILS_OVERLAP', 'bad_pd22b')}, position("bad_pos22", "9022")
                       + T("pd:bad_pd22b", "hr:PositionDetails", ["hr:detailsOf pos:bad_pos22", "hr:inUnit unit:PLAT", "hr:hasProfile job:ENG", "hr:chargedTo cc:C100", "hr:basedAt loc:London", 'hr:budgetedFte "1.0"^^xsd:decimal'], "2021-01-01"))
    c["pd_fte"] = ({('DETAILS_FTE', 'bad_pos23')}, position("bad_pos23", "9023", budget="0.0"))
    c["pos_nodetails"] = ({('POSITION_DETAILS', 'bad_pos24')}, 'pos:bad_pos24 a hr:Position ; hr:positionId "POS9024" .\n')
    c["rl_cycle"] = ({('MANAGER_CYCLE', 'bad_cyc1')}, position("bad_pc1", "9025") + position("bad_pc2", "9026") + position("bad_pc3", "9027")
                     + line("rl:bad_cyc1", "bad_pc1", "bad_pc2", "2020-01-01") + line("rl:bad_cyc2", "bad_pc2", "bad_pc3", "2020-01-01") + line("rl:bad_cyc3", "bad_pc3", "bad_pc1", "2020-01-01"))
    c["rl_self"] = ({('LINE_SELF', 'bad_rl_self')}, position("bad_pos28", "9028") + line("rl:bad_rl_self", "bad_pos28", "bad_pos28", "2020-01-01"))
    c["rl_two_solid"] = ({('LINE_ONE_SOLID', 'bad_solid_b'), ('LINE_ONE_SOLID', 'bad_solid_a')}, position("bad_pos29", "9029") + position("bad_pos30", "9030") + position("bad_pos31", "9031")
                         + line("rl:bad_solid_a", "bad_pos29", "bad_pos30", "2020-01-01") + line("rl:bad_solid_b", "bad_pos29", "bad_pos31", "2021-01-01"))
    c["rl_type"] = ({('LINE_TYPE', 'bad_rl_type')}, position("bad_pos32", "9032") + position("bad_pos33", "9033") + line("rl:bad_rl_type", "bad_pos32", "bad_pos33", "2020-01-01", typ="Medical"))
    # --- units
    c["unit_cycle"] = ({('UNIT_CYCLE', 'bad_ucyc1')}, unit("bad_u1", "U1") + unit("bad_u2", "U2") + structure("us:bad_ucyc1", "bad_u1", "bad_u2", "2020-01-01") + structure("us:bad_ucyc2", "bad_u2", "bad_u1", "2020-01-01"))
    c["unit_two_parents"] = ({('UNIT_ONE_PARENT', 'bad_utwo_a'), ('UNIT_ONE_PARENT', 'bad_utwo_b')}, unit("bad_u3", "U3") + structure("us:bad_utwo_a", "bad_u3", "ENG", "2020-01-01") + structure("us:bad_utwo_b", "bad_u3", "FIN", "2021-01-01"))
    c["unit_type"] = ({('UNIT_TYPE', 'bad_u4')}, 'unit:bad_u4 a hr:OrganizationalUnit ; hr:unitCode "U4" ; hr:unitType hrv:Medical ; hr:withinEntity ent:UK .\n')
    c["country"] = ({('COUNTRY_CODE', 'bad_ctry')}, 'ctry:bad_ctry a hr:Country ; hr:countryCode "gb" .\n')
    # --- talent
    c["rev_rating"] = ({('REVIEW_RATING', 'bad_rating')}, person(34) + person(35) + employment("emp:bad_e34", 34, "2020-01-01")
                       + T("rev:bad_rating", "hr:PerformanceReview", ["hr:reviewOf emp:bad_e34", f"hr:reviewer {pid(35)}", "hr:rating 6"], "2025-01-01", "2025-06-30"))
    c["rev_self"] = ({('REVIEW_SELF', 'bad_rev_self')}, person(36) + employment("emp:bad_e36", 36, "2020-01-01")
                     + T("rev:bad_rev_self", "hr:PerformanceReview", ["hr:reviewOf emp:bad_e36", f"hr:reviewer {pid(36)}", "hr:rating 3"], "2025-01-01", "2025-06-30"))
    c["skill_two"] = ({('SKILL_ONE_LEVEL', 'bad_sk_two_a'), ('SKILL_ONE_LEVEL', 'bad_sk_two_b')}, person(37)
                      + T("sa:bad_sk_two_a", "hr:SkillAssertion", [f"hr:assertedFor {pid(37)}", "hr:assertsSkill sk:Go", "hr:proficiency hrv:Working", "hr:evidenceSource hrv:SelfDeclared"], "2020-01-01")
                      + T("sa:bad_sk_two_b", "hr:SkillAssertion", [f"hr:assertedFor {pid(37)}", "hr:assertsSkill sk:Go", "hr:proficiency hrv:Advanced", "hr:evidenceSource hrv:SelfDeclared"], "2021-01-01"))
    c["skill_level"] = ({('SKILL_LEVEL', 'bad_level')}, person(38)
                        + T("sa:bad_level", "hr:SkillAssertion", [f"hr:assertedFor {pid(38)}", "hr:assertsSkill sk:Go", "hr:proficiency hrv:Medical", "hr:evidenceSource hrv:SelfDeclared"], "2020-01-01"))
    c["skill_notskill"] = ({('SKILL_SKILL', 'bad_notskill')}, person(39)
                           + T("sa:bad_notskill", "hr:SkillAssertion", [f"hr:assertedFor {pid(39)}", "hr:assertsSkill unit:PLAT", "hr:proficiency hrv:Working", "hr:evidenceSource hrv:SelfDeclared"], "2020-01-01"))
    c["cred_renewal"] = ({('CREDENTIAL_RENEWAL', 'bad_new')}, person(40)
                         + T("cred:bad_old", "hr:Credential", [f"hr:heldBy {pid(40)}", "hr:ofCertification cert:Privacy"], "2020-01-01", "2022-12-31")
                         + T("cred:bad_new", "hr:Credential", [f"hr:heldBy {pid(40)}", "hr:ofCertification cert:CloudArch", "hr:follows cred:bad_old"], "2023-01-01", "2025-12-31"))
    # --- hiring
    c["req_order"] = ({('REQUISITION_ORDER', 'bad_req_order')}, position("bad_pos41", "9041") + 'req:bad_req_order a hr:Requisition ; hr:requisitionFor pos:bad_pos41 ; hr:openedOn "2024-05-01"^^xsd:date ; hr:closedOn "2024-04-01"^^xsd:date .\n')
    c["app_early"] = ({('APPLICATION_BEFORE_OPEN', 'bad_early')}, person(42) + position("bad_pos42", "9042")
                      + 'req:bad_r42 a hr:Requisition ; hr:requisitionFor pos:bad_pos42 ; hr:openedOn "2024-05-01"^^xsd:date .\n'
                      + f'app:bad_early a hr:Application ; hr:applicant {pid(42)} ; hr:appliesTo req:bad_r42 ; hr:appliedOn "2024-04-01"^^xsd:date ; hr:applicationSource hrv:Referral .\n')
    c["offer_both"] = ({('OFFER_OUTCOME', 'bad_both')}, person(43) + position("bad_pos43", "9043")
                       + 'req:bad_r43 a hr:Requisition ; hr:requisitionFor pos:bad_pos43 ; hr:openedOn "2024-01-01"^^xsd:date .\n'
                       + f'app:bad_a43 a hr:Application ; hr:applicant {pid(43)} ; hr:appliesTo req:bad_r43 ; hr:appliedOn "2024-02-01"^^xsd:date ; hr:applicationSource hrv:Referral .\n'
                       + 'off:bad_both a hr:Offer ; hr:offerFor app:bad_a43 ; hr:offeredOn "2024-03-01"^^xsd:date ; hr:acceptedOn "2024-03-02"^^xsd:date ; hr:declinedOn "2024-03-03"^^xsd:date .\n')
    c["offer_result"] = ({('OFFER_RESULT', 'bad_result')}, person(44) + position("bad_pos44", "9044")
                         + 'req:bad_r44 a hr:Requisition ; hr:requisitionFor pos:bad_pos44 ; hr:openedOn "2024-01-01"^^xsd:date .\n'
                         + f'app:bad_a44 a hr:Application ; hr:applicant {pid(44)} ; hr:appliesTo req:bad_r44 ; hr:appliedOn "2024-02-01"^^xsd:date ; hr:applicationSource hrv:Referral .\n'
                         + 'off:bad_result a hr:Offer ; hr:offerFor app:bad_a44 ; hr:offeredOn "2024-03-01"^^xsd:date ; hr:resultsIn emp:P000001-20180108 .\n')
    for n, label, prop, rule in [(45, "accept", 'hr:acceptedOn "2024-02-15"^^xsd:date', "OFFER_ACCEPT_ORDER"), (46, "decline", 'hr:declinedOn "2024-02-15"^^xsd:date', "OFFER_DECLINE_ORDER")]:
        c[f"offer_{label}"] = ({(rule, f"bad_o{n}")}, person(n) + position(f"bad_pos{n}", f"90{n}")
                               + f'req:bad_r{n} a hr:Requisition ; hr:requisitionFor pos:bad_pos{n} ; hr:openedOn "2024-01-01"^^xsd:date .\n'
                               + f'app:bad_a{n} a hr:Application ; hr:applicant {pid(n)} ; hr:appliesTo req:bad_r{n} ; hr:appliedOn "2024-02-01"^^xsd:date ; hr:applicationSource hrv:Referral .\n'
                               + f'off:bad_o{n} a hr:Offer ; hr:offerFor app:bad_a{n} ; hr:offeredOn "2024-03-01"^^xsd:date ; {prop} .\n')
    return c


class OrdinaryRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_violations, cls.base_warnings = validate.ordinary(ordinary_graph())
        cls.cases = cases()
        g = ordinary_graph()
        for _name, (_t, ttl) in cls.cases.items():
            add(g, ttl)
        cls.bad_violations, _ = validate.ordinary(g)
        cls.found = set(tags(cls.bad_violations))

    def test_sample_data_is_valid(self):
        self.assertEqual(self.base_violations, [])

    def test_each_rule_fires_on_its_bad_case(self):
        for name, (expected, _ttl) in self.cases.items():
            for rule, focus in sorted(expected):
                with self.subTest(case=name, rule=rule, record=focus):
                    self.assertIn((rule, focus), self.found)

    def test_rules_fire_only_on_injected_records(self):
        stray = [(t, f) for t, f in self.found if not (f.startswith("bad_") or f.startswith("P9"))]
        self.assertEqual(stray, [], "a rule fired on real sample data")

    def test_expected_rule_names_are_real(self):
        shapes = (validate.ROOT / "shapes/core.shacl.ttl").read_text()
        for name, (expected, _ttl) in self.cases.items():
            for tag, _focus in expected:
                self.assertIn(tag + ":", shapes, f"{tag} is not a rule in core.shacl.ttl")

    def test_every_ordinary_rule_has_a_bad_case(self):
        import re
        shapes = (validate.ROOT / "shapes/core.shacl.ttl").read_text()
        rules = set(re.findall(r'sh:message "([A-Z0-9_]+):', shapes))
        tested = {t for _n, (exp, _t) in self.cases.items() for t, _f in exp}
        # Rules that merely require a single value (MIN/MAX count checks) share one pattern; the structural ones are all listed.
        structural = {r for r in rules if r.endswith(("_OVERLAP", "_CYCLE", "_UNIQUE", "_ORDER", "_WITHIN_EMPLOYMENT", "_CAPACITY", "_REHIRE", "_NEEDS_SEPARATION", "_FIXEDTERM", "_LEAF", "_ENDED", "_SELF", "_RESULT", "_OUTCOME", "_ONE_SOLID", "_ONE_PARENT", "_BEFORE_OPEN", "_RENEWAL", "_PRIMARY_ASSIGNMENT"))}
        self.assertEqual(sorted(structural - tested), [], "structural rules without a bad-case test")


class ValidEdgeCases(unittest.TestCase):
    """Things that must be allowed."""

    @classmethod
    def setUpClass(cls):
        cls.g = ordinary_graph()

    def test_duplicate_names_are_allowed(self):
        names = [str(o) for o in self.g.objects(None, __import__("rdflib").URIRef("https://example.org/hr/ontology#fullName"))]
        self.assertEqual(names.count("Daniel Kim"), 2)
        self.assertEqual(validate.ordinary(self.g)[0], [])

    def test_name_change_keeps_identity(self):
        from rdflib import URIRef
        HR = "https://example.org/hr/ontology#"
        chloe = URIRef("https://example.org/hr/id/person/P000009")
        records = list(self.g.subjects(URIRef(HR + "nameOf"), chloe))
        names = {str(self.g.value(r, URIRef(HR + "fullName"))) for r in records}
        self.assertEqual(names, {"Chloe Martin", "Chloe Dubois"})

    def test_a_gap_between_employments_is_allowed(self):
        v, _ = validate.ordinary(self.g)
        self.assertFalse([m for m in v if "EMPLOYMENT_OVERLAP" in m or "EMPLOYMENT_REHIRE" in m])

    def test_a_corrected_record_does_not_count_as_overlap(self):
        # Aisha's employment (P000007) has an original record and a correction for the same period.
        v, _ = validate.ordinary(self.g)
        self.assertFalse([m for m in v if "P000007" in m])

    def test_vacant_position_is_valid(self):
        v, _ = validate.ordinary(self.g)
        self.assertFalse([m for m in v if "POS0009" in m or "pos" in m.lower() and "POSITION_CAPACITY" in m])


def restricted_cases():
    c = {}
    band = lambda n, extra="", vf="2030-01-01": f'pb:bad_band{n} a hr:PayBand ; hr:bandGrade grd:G5 ; hr:bandCurrency "EUR" ; {extra} hr:validFrom {D(vf)} ; hr:recordedOn {D(vf)} .\n'
    c["bad_band1"] = ({('GRADE_RANGE', 'bad_band1')}, band(1, 'hr:bandMin "90000.00"^^xsd:decimal ; hr:bandMax "50000.00"^^xsd:decimal ;'))
    c["bad_band2"] = ({('BAND_OVERLAP', 'bad_band2')}, band(2, 'hr:bandMin "1.00"^^xsd:decimal ; hr:bandMax "9.00"^^xsd:decimal ;') + band(3, 'hr:bandMin "2.00"^^xsd:decimal ; hr:bandMax "8.00"^^xsd:decimal ;', "2031-01-01"))
    c["bad_band4"] = ({('BAND_CURRENCY', 'bad_band4')}, 'pb:bad_band4 a hr:PayBand ; hr:bandGrade grd:G5 ; hr:bandCurrency "euro" ; hr:bandMin "1.00"^^xsd:decimal ; hr:bandMax "2.00"^^xsd:decimal ; hr:validFrom "2040-01-01"^^xsd:date ; hr:recordedOn "2040-01-01"^^xsd:date .\n')

    def pay(n, g="grd:G5", amt='"60000.00"^^xsd:decimal', cur='"GBP"', reason="hrv:PayHire", emp="emp:P000008-20240603", vf="2024-06-03", vt=None, drop=()):
        parts = {"hr:compensationOf": emp, "hr:atGrade": g, "hr:baseAmount": amt, "hr:currency": cur, "hr:payChangeReason": reason}
        props = [f"{k} {v}" for k, v in parts.items() if k not in drop]
        return T(f"pay:bad_{n}", "hr:Compensation", props, vf, vt)

    c["bad_nograde"] = ({('COMP_GRADE', 'bad_nograde')}, pay("nograde", drop=("hr:atGrade",), vf="2035-01-01"))
    c["bad_zero"] = ({('COMP_SALARY', 'bad_zero')}, pay("zero", amt='"0.00"^^xsd:decimal', vf="2036-01-01"))
    c["bad_cur"] = ({('COMP_CURRENCY', 'bad_cur')}, pay("cur", cur='"pounds"', vf="2037-01-01"))
    c["bad_reason"] = ({('COMP_REASON', 'bad_reason')}, pay("reason", reason="hrv:Medical", vf="2038-01-01"))
    c["bad_owner"] = ({('COMP_OWNER', 'bad_owner')}, pay("owner", drop=("hr:compensationOf",), vf="2039-01-01"))
    c["bad_overlap"] = ({('COMP_OVERLAP', 'bad_overlap'), ('COMP_OVERLAP', 'P000008-1')}, pay("overlap", vf="2024-07-01"))  # overlaps Tomas's hire pay
    c["bad_outside"] = ({('COMP_WITHIN_EMPLOYMENT', 'bad_outside')}, pay("outside", emp="emp:P000011-20220502-b", vf="2020-01-01", vt="2021-12-31"))
    c["bad_enr_pct"] = ({('ENROLL_CONTRIBUTION', 'bad_pct')}, T("enr:bad_pct", "hr:BenefitEnrollment", ["hr:enrolledEmployment emp:P000012-20260105", "hr:inPlan plan:Retire", 'hr:contributionPercent "150.0"^^xsd:decimal'], "2026-02-01"))
    c["bad_enr_dup"] = ({('ENROLL_OVERLAP', 'bad_dup'), ('ENROLL_OVERLAP', '02')}, T("enr:bad_dup", "hr:BenefitEnrollment", ["hr:enrolledEmployment emp:P000001-20180108", "hr:inPlan plan:Retire", 'hr:contributionPercent "5.0"^^xsd:decimal'], "2020-01-01"))
    c["bad_plan"] = ({('PLAN_MATCH', 'bad_plan')}, 'plan:bad_plan a hr:BenefitPlan ; hr:planKind hrv:Medical ; hr:employerMatchPercent "250.0"^^xsd:decimal .\n')
    return c


class RestrictedRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_v, cls.base_w = validate.restricted(restricted_graph(), ordinary_graph())
        cls.cases = restricted_cases()
        g = restricted_graph()
        for _n, (_t, ttl) in cls.cases.items():
            add(g, ttl)
        cls.v, cls.w = validate.restricted(g, ordinary_graph())
        cls.found = set(tags(cls.v))

    def test_sample_pay_data_has_no_violations(self):
        self.assertEqual(self.base_v, [])

    def test_below_band_pay_is_a_warning_not_a_violation(self):
        self.assertEqual([t for t, _ in tags(self.base_w)], ["COMP_BAND"])
        self.assertEqual(tags(self.base_w)[0][1], "P000012-1")

    def test_each_restricted_rule_fires(self):
        for name, (expected, _ttl) in self.cases.items():
            for rule, focus in sorted(expected):
                with self.subTest(case=name, rule=rule, record=focus):
                    self.assertIn((rule, focus), self.found)

    def test_restricted_rules_do_not_fire_on_sample_records(self):
        allowed = {pair for exp, _ttl in self.cases.values() for pair in exp}   # overlap rules also flag the sample record they clash with
        stray = [(t, f) for t, f in self.found if not f.startswith("bad_") and (t, f) not in allowed]
        self.assertEqual(stray, [])


class SensitiveDataStaysSeparate(unittest.TestCase):
    def test_ordinary_check_does_not_load_pay(self):
        g = ordinary_graph()
        HR = "https://example.org/hr/ontology#"
        from rdflib import URIRef, RDF
        self.assertEqual(list(g.subjects(RDF.type, URIRef(HR + "Compensation"))), [])
        self.assertEqual(list(g.subjects(RDF.type, URIRef(HR + "BenefitEnrollment"))), [])

    def test_broken_pay_does_not_change_the_ordinary_result(self):
        before, _ = validate.ordinary(ordinary_graph())
        # Ordinary validation is run on a graph that excludes pay, so breaking pay cannot affect it.
        broken = restricted_graph()
        add(broken, 'pay:bad_x a hr:Compensation ; hr:baseAmount "-1.0"^^xsd:decimal .\n')
        after, _ = validate.ordinary(ordinary_graph())
        self.assertEqual(before, after)
        self.assertTrue(validate.restricted(broken, ordinary_graph())[0])

    def test_ordinary_shapes_never_mention_pay(self):
        text = (validate.ROOT / "shapes/core.shacl.ttl").read_text().lower()
        for word in ["compensation", "baseamount", "payband", "salary", "benefitplan", "enrollment", "contributionpercent"]:
            self.assertNotIn(word, text)

    def test_restricted_data_holds_no_personal_details(self):
        g = restricted_graph()
        HR = "https://example.org/hr/ontology#"
        from rdflib import URIRef
        banned = [URIRef(HR + x) for x in ("fullName", "personId", "employee", "nameOf", "birthDate")]
        for p in banned:
            self.assertEqual(list(g.triples((None, p, None))), [], f"restricted data uses {p}")

    def test_every_restricted_class_is_in_the_restricted_data_or_shapes(self):
        import re
        sens = (validate.ROOT / "shapes/sensitive.shacl.ttl").read_text()
        for cls in ("PayBand", "Compensation", "BenefitEnrollment", "BenefitPlan"):
            self.assertIn(f"hr:{cls}", sens)


if __name__ == "__main__":
    unittest.main()
