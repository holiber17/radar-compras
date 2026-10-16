import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone

from tracker import db
from tracker.providers.base import ParseError
from tracker.providers.camelcamelcamel import looks_blocked, parse_product_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "product_B00S0BEUIY.html")


def load():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


class ParserTests(unittest.TestCase):
    def test_reads_all_prices(self):
        s = parse_product_html("B00S0BEUIY", load())
        self.assertEqual(s.title, "Shenzhen Knives Electric Diamond Knife Sharpener for Ceramic Knives")
        self.assertEqual(s.amazon_current, 22.99)
        self.assertEqual(s.amazon_lowest, 22.99)
        self.assertEqual(s.amazon_highest, 75.00)
        self.assertEqual(s.amazon_avg, 51.09)
        self.assertEqual(s.amazon_highest_date, date(2022, 7, 20))
        self.assertEqual(s.new_current, 22.99)
        self.assertIsNone(s.used_current)  # el guion significa "sin precio"
        self.assertEqual(s.observed_at, datetime(2026, 10, 11, 13, 37))

    def test_missing_table_fails_loudly(self):
        with self.assertRaises(ParseError):
            parse_product_html("B00S0BEUIY", "<html><body><p>Otra cosa</p></body></html>")

    def test_empty_table_fails_loudly(self):
        html = load().replace("$", "")  # simula que cambió el formato de las cifras
        with self.assertRaises(ParseError):
            parse_product_html("B00S0BEUIY", html)

    def test_thousands_separator(self):
        html = load().replace("$75.00", "$1,075.00")
        self.assertEqual(parse_product_html("B00S0BEUIY", html).amazon_highest, 1075.00)

    def test_block_detection(self):
        self.assertTrue(looks_blocked(429, ""))
        self.assertTrue(looks_blocked(200, "<title>Just a moment...</title>"))
        self.assertFalse(looks_blocked(200, load()))


class DbTests(unittest.TestCase):
    def test_save_and_latest(self):
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(os.path.join(d, "t.db"))
            snap = parse_product_html("B00S0BEUIY", load(), fetched_at=datetime.now(timezone.utc))
            db.save(conn, snap)
            rows = db.latest(conn, "B00S0BEUIY")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["amazon_current"], 22.99)
            self.assertTrue(db.fetched_within(conn, "B00S0BEUIY", 12))
            self.assertFalse(db.fetched_within(conn, "B0OTHERASIN", 12))
            conn.close()


if __name__ == "__main__":
    unittest.main()
