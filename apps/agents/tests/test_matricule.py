from django.test import SimpleTestCase

from apps.agents.matricule import format_matricule


class MatriculeFormatTests(SimpleTestCase):
    def test_groups_digits_by_thousands(self):
        self.assertEqual(format_matricule("1515048"), "1.515.048")
        self.assertEqual(format_matricule("1297433-2"), "1.297.433-2")

    def test_leaves_codes_unchanged(self):
        self.assertEqual(format_matricule("DTMF-001"), "DTMF-001")
        self.assertEqual(format_matricule(""), "—")
