"""Semantic layer tests: every metric gives the answer worked out by hand from the sample data,
including answers "as of" a past day and "as known" on a past day."""
import unittest
from datetime import date
from decimal import Decimal

from tests.support import metrics_graph, layer


class Metrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = metrics_graph(sensitive=True)

    def run_metric(self, name, **params):
        return layer.run(self.g, name, **params)

    def test_headcount_today_and_in_the_past(self):
        self.assertEqual(self.run_metric("headcount", asOf="2026-10-31")[0]["headcount"], 12)
        self.assertEqual(self.run_metric("headcount", asOf="2024-01-01")[0]["headcount"], 10)
        self.assertEqual(self.run_metric("headcount", asOf="2023-01-01")[0]["headcount"], 8)

    def test_a_leaver_is_not_counted_after_the_last_day_but_is_on_it(self):
        self.assertEqual(self.run_metric("headcount", asOf="2024-02-29")[0]["headcount"], 11)
        self.assertEqual(self.run_metric("headcount", asOf="2024-03-01")[0]["headcount"], 10)

    def test_fte(self):
        self.assertEqual(self.run_metric("fte", asOf="2026-10-31")[0]["totalFte"], Decimal("11.8"))

    def test_fte_as_known_before_and_after_a_correction(self):
        # Aisha's FTE was recorded as 1.0 and corrected to 0.8 on 2023-06-01, for a period starting 2023-01-09.
        before = self.run_metric("fte", asOf="2023-05-01", known="2023-05-01")[0]["totalFte"]
        after = self.run_metric("fte", asOf="2023-05-01", known="2026-10-31")[0]["totalFte"]
        self.assertEqual((before, after), (Decimal("9.5"), Decimal("9.3")))

    def test_headcount_by_unit_rolls_up(self):
        rows = {r["unitCode"]: r["headcount"] for r in self.run_metric("headcount_by_unit", asOf="2026-10-31")}
        self.assertEqual(rows, {"DATA": 3, "ENG": 4, "EXEC": 12, "FIN": 2, "PEOP": 2, "PLAT": 3, "RECR": 1})

    def test_headcount_by_unit_follows_the_reorganisation(self):
        before = {r["unitCode"]: r["headcount"] for r in self.run_metric("headcount_by_unit", asOf="2025-06-30")}
        after = {r["unitCode"]: r["headcount"] for r in self.run_metric("headcount_by_unit", asOf="2025-07-01")}
        self.assertEqual(before["ENG"], 7)   # Data & AI still sat under Engineering
        self.assertEqual(after["ENG"], 4)    # moved to the Executive Office on 2025-07-01
        self.assertEqual(before["DATA"], after["DATA"])

    def test_leavers_with_reason_and_category(self):
        rows = self.run_metric("leavers", periodStart="2022-01-01", periodEnd="2026-12-31")
        self.assertEqual([(r["personId"], r["lastDay"], r["reasonLabel"], r["categoryLabel"]) for r in rows],
                         [("P000013", date(2023, 9, 30), "Resignation", "Voluntary"),
                          ("P000011", date(2024, 2, 29), "Redundancy", "Involuntary")])

    def test_leaver_names_show_with_ids(self):
        rows = self.run_metric("leavers", periodStart="2024-01-01", periodEnd="2024-12-31")
        self.assertEqual([(r["personId"], r["name"]) for r in rows], [("P000011", "Daniel Kim")])

    def test_leavers_as_known_on_an_earlier_day(self):
        self.assertEqual(self.run_metric("leavers", periodStart="2022-01-01", periodEnd="2026-12-31", known="2023-08-01"), [])
        one = self.run_metric("leavers", periodStart="2022-01-01", periodEnd="2026-12-31", known="2023-09-01")
        self.assertEqual([r["personId"] for r in one], ["P000013"])

    def test_attrition_rate(self):
        r = self.run_metric("attrition_rate", periodStart="2024-01-01", periodEnd="2024-12-31")[0]
        self.assertEqual((r["leavers"], r["headcountStart"], r["headcountEnd"]), (1, 10, 11))
        self.assertAlmostEqual(float(r["rate"]), 1 / 10.5, places=6)
        r = self.run_metric("attrition_rate", periodStart="2023-01-01", periodEnd="2023-12-31")[0]
        self.assertEqual((r["leavers"], r["headcountStart"], r["headcountEnd"]), (1, 8, 10))
        self.assertAlmostEqual(float(r["rate"]), 1 / 9, places=6)

    def test_attrition_with_no_leavers_is_zero(self):
        r = self.run_metric("attrition_rate", periodStart="2025-01-01", periodEnd="2025-12-31")[0]
        self.assertEqual(r["leavers"], 0)
        self.assertEqual(float(r["rate"]), 0.0)

    def test_attrition_by_category(self):
        rows = {r["categoryLabel"]: r["leavers"] for r in self.run_metric("attrition_by_category", periodStart="2022-01-01", periodEnd="2026-12-31")}
        self.assertEqual(rows, {"Voluntary": 1, "Involuntary": 1})

    def test_rehires(self):
        self.assertEqual(self.run_metric("rehires", asOf="2026-10-31"),
                         [{"personId": "P000013", "left": date(2023, 9, 30), "returned": date(2024, 1, 15)}])

    def test_tenure_restarts_for_a_rehire(self):
        years = {r["personId"]: r["years"] for r in self.run_metric("tenure", asOf="2026-10-31")}
        self.assertEqual(years["P000001"], 8)
        self.assertEqual(years["P000013"], 2)   # back since 2024-01-15; the first spell is not added
        self.assertEqual(years["P000012"], 0)
        self.assertNotIn("P000011", years)       # the leaver

    def test_the_two_daniel_kims_are_told_apart_by_id(self):
        names = [(r["personId"], r["name"]) for r in self.run_metric("tenure", asOf="2023-06-01") if r["name"] == "Daniel Kim"]
        self.assertEqual(sorted(names), [("P000006", "Daniel Kim"), ("P000011", "Daniel Kim")])

    def test_name_change_shows_the_name_valid_on_the_day(self):
        before = {r["personId"]: r["name"] for r in self.run_metric("tenure", asOf="2024-01-01")}
        after = {r["personId"]: r["name"] for r in self.run_metric("tenure", asOf="2026-10-31")}
        self.assertEqual((before["P000009"], after["P000009"]), ("Chloe Martin", "Chloe Dubois"))

    def test_span_of_control(self):
        rows = {r["managerId"]: r["directReports"] for r in self.run_metric("span_of_control", asOf="2026-10-31")}
        self.assertEqual(rows, {"P000001": 4, "P000002": 1, "P000003": 2, "P000004": 1, "P000005": 1, "P000006": 2})

    def test_span_of_control_ignores_dotted_lines(self):
        # Ravi (P000010) has a dotted line to Daniel Kim's position; Daniel still has only two solid-line reports.
        rows = {r["managerId"]: r["directReports"] for r in self.run_metric("span_of_control", asOf="2026-10-31")}
        self.assertEqual(rows["P000006"], 2)

    def test_span_of_control_follows_the_reorganisation(self):
        before = {r["managerId"]: r["directReports"] for r in self.run_metric("span_of_control", asOf="2025-06-30")}
        after = {r["managerId"]: r["directReports"] for r in self.run_metric("span_of_control", asOf="2025-07-01")}
        self.assertEqual((before["P000002"], before["P000001"]), (2, 3))
        self.assertEqual((after["P000002"], after["P000001"]), (1, 4))

    def test_vacancy(self):
        rows = [(r["positionId"], r["unfilledFte"]) for r in self.run_metric("vacancy", asOf="2026-10-31")]
        self.assertEqual(rows, [("POS0009", Decimal("1.0")), ("POS0007", Decimal("0.2"))])

    def test_a_closed_position_is_not_a_vacancy(self):
        ids = [r["positionId"] for r in self.run_metric("vacancy", asOf="2026-10-31")]
        self.assertNotIn("POS0010", ids)         # closed on 2025-03-31 when its holder was promoted
        ids_then = [r["positionId"] for r in self.run_metric("vacancy", asOf="2025-03-01")]
        self.assertNotIn("POS0010", ids_then)    # it was filled then

    def test_a_seat_between_holders_is_vacant(self):
        rows = {r["positionId"]: r["unfilledFte"] for r in self.run_metric("vacancy", asOf="2024-04-01")}
        self.assertEqual(rows["POS0008"], Decimal("1.0"))   # the leaver left on 2024-02-29; the next hire starts 2024-06-03

    def test_time_to_fill(self):
        rows = self.run_metric("time_to_fill")
        self.assertEqual([(r["requisition"], r["days"]) for r in rows], [("R001", 91)])

    def test_expiring_credentials(self):
        rows = self.run_metric("expiring_credentials", asOf="2026-10-31", withinDays=60)
        self.assertEqual([(r["personId"], r["expires"]) for r in rows], [("P000010", date(2026, 11, 30))])
        self.assertEqual(self.run_metric("expiring_credentials", asOf="2026-10-31", withinDays=10), [])

    def test_a_renewed_credential_is_not_expiring(self):
        rows = self.run_metric("expiring_credentials", asOf="2025-05-01", withinDays=60)
        self.assertEqual(rows, [])   # Aisha's cloud certificate ends 2025-05-31 but was renewed

    def test_pay_outside_band(self):
        rows = self.run_metric("pay_outside_band", asOf="2026-10-31")
        self.assertEqual([(r["personId"], r["grade"], r["amount"]) for r in rows], [("P000012", "G4", Decimal("47000.00"))])

    def test_average_pay_never_mixes_currencies(self):
        rows = {(r["unitCode"], r["cur"]): (r["people"], r["average"]) for r in self.run_metric("average_pay_by_unit", asOf="2026-10-31")}
        self.assertEqual(rows[("FIN", "USD")], (2, Decimal("82500.00")))
        self.assertEqual(rows[("DATA", "GBP")], (3, Decimal("86000.00")))
        self.assertTrue(all(cur in ("GBP", "USD") for _u, cur in rows))

    def test_average_pay_as_known_before_and_after_a_correction(self):
        # Aisha's first pay record (86,000) was corrected to 76,000 on 2023-07-03 for the same period.
        before = {(r["unitCode"]): r["average"] for r in self.run_metric("average_pay_by_unit", asOf="2023-07-01", known="2023-07-01")}
        after = {(r["unitCode"]): r["average"] for r in self.run_metric("average_pay_by_unit", asOf="2023-07-01", known="2026-10-31")}
        self.assertEqual((before["PLAT"], after["PLAT"]), (Decimal("89000"), Decimal("84000")))


class LayerBehaviour(unittest.TestCase):
    def test_missing_parameter_is_an_error(self):
        with self.assertRaises(ValueError):
            layer.build_query("headcount", {})

    def test_unknown_metric_is_an_error(self):
        with self.assertRaises(KeyError):
            layer.metric_path("no_such_metric")

    def test_every_metric_expands_with_no_leftover_placeholders(self):
        dummy = {"asOf": "2026-01-01", "periodStart": "2026-01-01", "periodEnd": "2026-12-31", "withinDays": "30"}
        for m in layer.list_metrics():
            q, _ = layer.build_query(m, dummy)
            self.assertNotIn("#include", q, m)
            self.assertNotIn("@{", q, m)
            for var in ("?asOf", "?known", "?periodStart", "?periodEnd", "?withinDays", "?horizon"):
                self.assertNotIn(var, q, f"{m} still has {var}")

    def test_validity_logic_lives_only_in_fragments(self):
        """'Valid on a day' and 'current employee' are defined once, in fragments, never copied into a metric."""
        for m in layer.list_metrics():
            text = layer.metric_path(m).read_text()
            self.assertNotIn("9999-12-31", text, f"{m} restates the validity rule")
            self.assertNotIn("hr:supersedes", text, f"{m} restates the correction rule")
        users = [m for m in layer.list_metrics() if "#include ActiveEmployment" in layer.metric_path(m).read_text()]
        self.assertGreaterEqual(len(users), 8)


if __name__ == "__main__":
    unittest.main()
