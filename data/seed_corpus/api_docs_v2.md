# Acme Platform API Documentation — Version 2.0 (CURRENT)

## Overview

The Acme Platform API provides programmatic access to all platform resources.
Base URL: `https://api.acme.io/v2`

This is the current stable API. Version 1 is deprecated and will be sunset on 2025-06-01.

## Authentication

The API uses **OAuth 2.0 with JWT bearer tokens**. API key authentication is no longer supported.

To authenticate:
1. Register your application in the developer portal.
2. Obtain a client_id and client_secret.
3. Exchange credentials for an access token:

```
POST https://auth.acme.io/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=YOUR_ID&client_secret=YOUR_SECRET
```

4. Include the token in all API requests:
```
Authorization: Bearer YOUR_JWT_TOKEN
```

Tokens expire after 1 hour. Refresh using your client credentials before expiry.

## Rate Limits

Rate limits vary by subscription tier:

| Tier | Rate Limit | Burst |
|------|-----------|-------|
| Free | 100 req/min | No burst |
| Pro | 1,000 req/min | 5,000 req/30s burst |
| Enterprise | 10,000 req/min | Custom burst |

Exceeding limits returns HTTP 429 with a `Retry-After` header.

## Endpoints

### GET /users
Returns paginated list of users. Supports cursor-based pagination.

**Response:**
```json
{
  "users": [{"id": "usr_123", "email": "alice@acme.io", "role": "admin", "mfa_enabled": true}],
  "next_cursor": "eyJpZCI6MTIzfQ==",
  "total": 1
}
```

### POST /documents
Upload a document. Supports multiple formats including PDF.

**Request body:**
```json
{"title": "My Doc", "content": "...", "format": "pdf", "tags": ["engineering"]}
```

Supported formats: `text`, `html`, `pdf`, `markdown`.

### POST /search
Hybrid semantic + keyword search across all documents.

**Request body:**
```json
{"query": "API authentication", "top_k": 10, "mode": "hybrid"}
```

Modes: `semantic` (vector search), `keyword` (BM25), `hybrid` (recommended).

### GET /documents/{id}/chunks
Retrieve chunked representations of a document for RAG use cases.

## Error Handling

All error responses include a structured body:

```json
{"error": "message", "code": "ERROR_CODE", "details": {"field": "reason"}, "request_id": "req_abc"}
```

The `details` and `request_id` fields are always present.

## Data Retention

Documents are retained for **7 years** by default to meet compliance requirements.
Shorter retention can be configured per workspace in Settings > Data Policy.

## SDKs

Official SDKs: Python, JavaScript/TypeScript, Go, Java.
Community SDKs: Ruby, PHP, Rust.

## Webhooks

v2 adds webhook support for real-time event notifications. Configure endpoints at Settings > Webhooks.

## Support

- Documentation: https://docs.acme.io
- Status page: https://status.acme.io
- Support: support@acme.io (SLA: 4h Pro, 1h Enterprise)

Last updated: 2025-03-20
