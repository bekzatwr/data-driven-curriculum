"""Compatibility exports for the single synthetic demo shared by all modules."""
import csv
import io
from analytics.demo import METADATA, demo_files


def csv_bytes(fields, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")
