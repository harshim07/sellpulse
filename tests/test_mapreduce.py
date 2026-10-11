import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAPPER = ROOT / "mapreduce" / "mapper.py"
REDUCER = ROOT / "mapreduce" / "reducer.py"


def run_script(script, input_text):
    return subprocess.run(
        [sys.executable, str(script)],
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


def transaction(product_name, units_sold):
    return json.dumps(
        {"product_name": product_name, "units_sold": units_sold}
    )


class MapperTests(unittest.TestCase):
    def test_valid_transactions_emit_tab_separated_pairs(self):
        result = run_script(
            MAPPER,
            transaction(" Widget ", 4) + "\n" + transaction("Gadget", 0) + "\n",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Widget\t4\nGadget\t0\n")

    def test_invalid_json_is_reported_with_line_number(self):
        result = run_script(MAPPER, "not-json\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("input line 1", result.stderr)

    def test_non_object_json_is_rejected(self):
        result = run_script(MAPPER, "[]\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("JSON object", result.stderr)

    def test_missing_required_fields_are_rejected(self):
        for record in ({"units_sold": 1}, {"product_name": "Widget"}):
            with self.subTest(record=record):
                result = run_script(MAPPER, json.dumps(record) + "\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("input line 1", result.stderr)

    def test_empty_product_name_is_rejected(self):
        result = run_script(MAPPER, transaction("  ", 1) + "\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("product_name cannot be empty", result.stderr)

    def test_non_text_product_name_is_rejected(self):
        result = run_script(MAPPER, transaction(123, 1) + "\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("product_name must be text", result.stderr)

    def test_boolean_quantity_is_rejected(self):
        result = run_script(MAPPER, '{"product_name":"Widget","units_sold":true}\n')

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("units_sold must be an integer", result.stderr)

    def test_fractional_quantities_are_rejected(self):
        for quantity in (1.5, 2.0):
            with self.subTest(quantity=quantity):
                result = run_script(MAPPER, transaction("Widget", quantity) + "\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("units_sold must be an integer", result.stderr)

    def test_negative_quantity_is_rejected(self):
        result = run_script(MAPPER, transaction("Widget", -1) + "\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("units_sold cannot be negative", result.stderr)

    def test_product_tabs_and_line_breaks_are_rejected(self):
        for product in ("Widget\tPro", "Widget\nPro", "Widget\rPro"):
            with self.subTest(product=product):
                result = run_script(MAPPER, transaction(product, 1) + "\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("cannot contain tabs or line breaks", result.stderr)


class ReducerTests(unittest.TestCase):
    def test_duplicate_products_are_aggregated_and_ranked(self):
        result = run_script(
            REDUCER,
            "Beta\t3\nAlpha\t5\nBeta\t4\nGamma\t9\n",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            list(csv.reader(io.StringIO(result.stdout))),
            [
                ["rank", "product_name", "units_sold"],
                ["1", "Gamma", "9"],
                ["2", "Beta", "7"],
                ["3", "Alpha", "5"],
            ],
        )

    def test_alphabetical_order_breaks_equal_total_ties(self):
        result = run_script(REDUCER, "Zulu\t8\nAlpha\t8\nMiddle\t8\n")

        rows = list(csv.reader(io.StringIO(result.stdout)))
        self.assertEqual([row[1] for row in rows[1:]], ["Alpha", "Middle", "Zulu"])

    def test_more_than_ten_products_are_truncated(self):
        data = "".join("Product{:02d}\t{}\n".format(index, index) for index in range(12))
        result = run_script(REDUCER, data)

        self.assertEqual(result.returncode, 0, result.stderr)
        rows = list(csv.reader(io.StringIO(result.stdout)))
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[1][1], "Product11")
        self.assertEqual(rows[-1][1], "Product02")

    def test_fewer_than_ten_products_are_all_returned(self):
        result = run_script(REDUCER, "Solo\t6\nPair\t2\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        rows = list(csv.reader(io.StringIO(result.stdout)))
        self.assertEqual(len(rows), 3)
        self.assertEqual([row[1] for row in rows[1:]], ["Solo", "Pair"])

    def test_empty_input_emits_header_only(self):
        result = run_script(REDUCER, "")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            list(csv.reader(io.StringIO(result.stdout))),
            [["rank", "product_name", "units_sold"]],
        )

    def test_malformed_reducer_records_are_rejected(self):
        malformed = (
            "missing-separator\n",
            "\t4\n",
            " Padded\t4\n",
            "Bad\textra\t4\n",
            "Bad\t4\textra\n",
        )
        for record in malformed:
            with self.subTest(record=record):
                result = run_script(REDUCER, record)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("mapper output on line 1", result.stderr)

    def test_invalid_and_negative_quantities_are_rejected(self):
        for record in ("Widget\tnope\n", "Widget\t-1\n", "Widget\t+1\n"):
            with self.subTest(record=record):
                result = run_script(REDUCER, record)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("non-negative integer", result.stderr)

    def test_csv_escaping_preserves_commas_and_quotes(self):
        product = 'Widget, "Pro"'
        result = run_script(REDUCER, product + "\t12\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        rows = list(csv.reader(io.StringIO(result.stdout)))
        self.assertEqual(rows[1], ["1", product, "12"])
        self.assertIn('"Widget, ""Pro"""', result.stdout)


class PipelineTests(unittest.TestCase):
    def test_mapper_to_reducer_execution(self):
        jsonl = "\n".join(
            (
                transaction("Pear", 4),
                transaction("Apple", 3),
                transaction("Pear", 5),
            )
        ) + "\n"
        mapped = run_script(MAPPER, jsonl)
        self.assertEqual(mapped.returncode, 0, mapped.stderr)

        reduced = run_script(REDUCER, mapped.stdout)
        self.assertEqual(reduced.returncode, 0, reduced.stderr)
        self.assertEqual(
            list(csv.reader(io.StringIO(reduced.stdout))),
            [
                ["rank", "product_name", "units_sold"],
                ["1", "Pear", "9"],
                ["2", "Apple", "3"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
