# X12 EDI Integration Pipeline

A runnable Python portfolio project that processes **synthetic X12 204 load tenders, 210 freight invoices, and 214 shipment status messages**. It demonstrates local ingestion, validation, JSON transformation, error quarantine, duplicate detection, and operational monitoring.

All partners, shipments, invoices, addresses, and amounts are fictional. This is an independent demonstration inspired by common freight integration workflows; it contains no employer source code or production data.

## Quick start

Requires Python 3.10 or later. No paid services, API keys, or runtime dependencies.

```bash
git clone https://github.com/abdulrlmohammed9/edi-x12-integration-pipeline.git
cd edi-x12-integration-pipeline
python -m edi_pipeline --input samples --output output
python -m unittest discover -s tests -v
```

On Windows, use `py` instead of `python` if needed. These commands work in PowerShell, a terminal, PyCharm, or GitHub Codespaces. Optional installation: `python -m pip install -e .`; then use `x12-pipeline` with the same arguments.

Open `output/dashboard.html` in a browser for monitoring. It is a static report regenerated after each run. No web server is required.

## Architecture

```mermaid
flowchart TD
    A[Sample X12 files] --> B[Envelope and business validation]
    B -->|Valid| C[Normalized JSON]
    B -->|Invalid| D[Original file and error quarantine]
    C --> E[SQLite history and dashboard]
    D --> E
```

SHA-256 checks against SQLite skip previously processed identical bytes before validation. Original input files are left in place. Correct a rejected file in a separate input folder and rerun; changed bytes create a new history entry. To deliberately replay identical bytes for a demonstration, choose a new output folder.

## Implemented mappings

| Transaction | Input fields | JSON output |
|---|---|---|
| 204 | B202, B204, B206, S501/S502 | Carrier, shipment, payment method, stop sequence/reason |
| 210 | B302/B303/B306/B307/B311, C301 | Invoice, shipment, date, amount, carrier, currency |
| 214 | B1001–B1003, AT701/AT705–AT707 | Shipment, BOL, carrier, status, local event date/time/time code |

Invoice amounts use decimal arithmetic with B307 interpreted as implied cents. L305 must match B307. AT7 time codes are retained; timestamps are not converted to UTC because the sample profile does not resolve geographic time zones.

## Validation scope

The deliberately narrow demo profile accepts ASCII, test-only (`ISA15=T`), version 004010, one interchange containing one group and one transaction per file. It discovers separators from a fixed-width 106-character ISA header.

Checks include envelope nesting, required envelope occurrences, ISA/IEA, GS/GE and ST/SE control matching, SE segment count, GE/IEA counts, supported transaction and functional identifiers, required business segments/selected fields, valid invoice/event dates, nonnegative integer invoice cents, matching invoice totals, and the supported AT7 status subset X1/X3/X6/AF/D1.

This is **selected validation for a sample profile**, not complete X12 syntax or partner implementation-guide certification. Unmapped segments are not fully validated. Multiple interchanges/groups/transactions are rejected. Business identifier deduplication across different interchanges is not implemented; replay protection is byte based.

## Outputs

| Path | Purpose |
|---|---|
| `output/accepted/<sha256>.json` | Normalized business record plus provenance |
| `output/quarantine/<sha256>.edi` | Original rejected bytes |
| `output/quarantine/<sha256>.error.json` | Validation reason and provenance |
| `output/monitoring.sqlite` | Persistent unique-file processing history |
| `output/events.jsonl` | Accepted/rejected processing events |
| `output/summary.json` | Last-run counts and cumulative unique-file outcomes |
| `output/dashboard.html` | Outcome totals, file history, errors, latency, timestamps |

Run a valid-only batch with a nonzero exit on newly rejected files:

```bash
python -m edi_pipeline --input samples/valid --output output-valid --fail-on-rejection
```

A mixed sample batch intentionally includes rejected files and exits successfully unless `--fail-on-rejection` is supplied. Duplicate skips do not re-emit event log entries. Processing latency excludes final dashboard generation. Infrastructure failures such as unreadable inputs or unwritable outputs stop the command rather than misclassifying a file as invalid EDI.

## Verified demonstration

Locally verified on Python 3.12 on November 5, 2026:

- 10 automated tests passed.
- First mixed batch: **3 accepted, 3 rejected**.
- Repeated identical batch: **6 duplicates skipped**, no additional accepted records.
- Valid-only CLI batch: **3 accepted, 0 rejected**.

Tests cover the three mappings, alternate delimiters, malformed/truncated envelopes, missing business segments, invalid dates/status/amounts, mismatched totals/control counts, production/multiple-interchange rejection, quarantine artifacts, and persistent replay protection. GitHub Actions is configured for Python 3.10 and 3.12; local verification is distinct from hosted CI results.

## Operational limits and future work

Run one process per output directory. SQLite commits per file and atomic JSON replacement help local use, but file writes and database records are not one distributed transaction; this is not an exactly-once production system. The dashboard and history are unbounded for a small portfolio demonstration.

Future work: partner-configurable rules and full implementation-guide validation; multi-transaction splitting; business-key duplicate detection; 997/999 acknowledgments; SFTP/AS2 ingress; scheduled ingestion; alert thresholds; retention and retry policies; database/output transaction coordination; and optional cloud deployment. These integrations are not implemented or claimed as live capabilities.

## License

See [LICENSE](LICENSE).
