# IDR Backend — Scanner API

Flask REST API for the IDR Shield accessibility scanner.

## Endpoints
- GET /api/status — health check
- POST /api/scan — run a scan
- POST /api/activate — activation + scan
- GET /api/receipt/<id> — retrieve receipt
- POST /api/verify — verify receipt integrity
- GET /api/registry/<domain> — registry lookup
