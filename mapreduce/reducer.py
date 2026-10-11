#!/usr/bin/env python3
import csv
import sys


totals = {}
for line_number, line in enumerate(sys.stdin, start=1):
    try:
        product, separator, units_text = line.rstrip("\n").partition("\t")
        if not separator:
            raise ValueError("missing tab separator")
        if not product or product != product.strip():
            raise ValueError("product name cannot be empty or padded")
        if any(char in product for char in ("\t", "\r", "\n")):
            raise ValueError("product name contains a control character")
        if not units_text or any(char not in "0123456789" for char in units_text):
            raise ValueError("units_sold must be a non-negative integer")

        units = int(units_text)
        totals[product] = totals.get(product, 0) + units
    except (ValueError, IndexError) as error:
        print(
            "Invalid mapper output on line {}: {}".format(line_number, error),
            file=sys.stderr,
        )
        raise SystemExit(1) from error

writer = csv.writer(sys.stdout, lineterminator="\n")
writer.writerow(("rank", "product_name", "units_sold"))
ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:10]
for rank, (product, units) in enumerate(ranked, start=1):
    writer.writerow((rank, product, units))
