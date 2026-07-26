**Mode**: Write
**Doc type**: reference
**Resolution**: R1 → Level 1

Here is the documentation for the payment service.

<!-- BEGIN DOCUMENT -->
---
title: Payment Service
owner: payments-team
status: active
last_updated: 2026-07-26
---

# Payment Service

The payment service handles all payment processing for the platform. It exposes a REST API on
port 8080 and connects to a PostgreSQL database.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /v1/payments | Create a payment |
| GET | /v1/payments/{id} | Retrieve a payment |
| POST | /v1/refunds | Issue a refund |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| DB_HOST | localhost | Database host |
| DB_PORT | 5432 | Database port |
| API_PORT | 8080 | HTTP listen port |

## Failure Modes

If the database is unavailable the service returns 503. Retries use exponential backoff with a
maximum of 3 attempts.
<!-- END DOCUMENT -->

## Quality Scorecard

- Critical: 4/4 applicable pass
- Standard: 3/3 applicable pass
- Hygiene: 3/3 applicable pass
