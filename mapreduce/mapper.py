#!/usr/bin/env python3
import json
import sys


for line_number, line in enumerate(sys.stdin, start=1):
    try:
        transaction = json.loads(line)
        if not isinstance(transaction, dict):
            raise ValueError("transaction must be a JSON object")

        product_value = transaction["product_name"]
        units = transaction["units_sold"]
        if not isinstance(product_value, str):
            raise ValueError("product_name must be text")
        product = product_value.strip()
        if not product:
            raise ValueError("product_name cannot be empty")
        if any(char in product for char in ("\t", "\n", "\r")):
            raise ValueError("product_name cannot contain tabs or line breaks")
        if isinstance(units, bool) or not isinstance(units, int):
            raise ValueError("units_sold must be an integer")
        if units < 0:
            raise ValueError("units_sold cannot be negative")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(
            "Invalid HDFS transaction on input line {}: {}".format(
                line_number, error
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from error

    print("{}\t{}".format(product, units))
