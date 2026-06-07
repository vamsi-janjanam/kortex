# Acme Platform API Documentation — Version 1.0 (DEPRECATED)

> ⚠️ This document is outdated. Refer to api_docs_v2.md for current information.

## Overview

The Acme Platform API provides programmatic access to all platform resources.
Base URL: `https://api.acme.io/v1`

## Authentication

The API uses **API Key authentication**. Include your API key in every request header:

```
Authorization: ApiKey YOUR_API_KEY_HERE
```

API keys are 32-character alphanumeric strings issued from the developer portal.
Keys do not expire and must be rotated manually by the account administrator.

There is no OAuth support. Do not attempt to use OAuth tokens with this API.

## Rate Limits

All endpoints are rate limited to **50 requests per minute** per API key.
Exceeding this limit returns HTTP 429. There is no burst allowance.

| Tier | Rate Limit |
|------|-----------|
| Free | 50 req/min |
| Pro | 50 req/min |
| Enterprise | 50 req/min |

## Endpoints

### GET /users
Returns a list of all users in the organization.

**Response:**
```json
{
  "users": [{"id": "usr_123", "email": "alice@acme.io", "role": "admin"}],
  "total": 1
}
```

### POST /documents
Upload a new document.

**Request body:**
```json
{"title": "My Doc", "content": "...", "format": "text"}
```

Supported formats: `text`, `html`. PDF is not supported in v1.

### GET /search
Full-text search across all documents.

**Parameters:**
- `q` (string, required): Search query
- `limit` (int): Max results, default 10, max 50

Returns ranked results by keyword relevance only. Vector/semantic search is not available.

## Error Handling

The API returns standard HTTP status codes. Error responses use this format:

```json
{"error": "message", "code": "ERROR_CODE"}
```

**Note:** The `details` field is not present in v1 error responses.

## Data Retention

Documents are retained for **30 days** by default. Extended retention requires contacting support.

## SDKs

Official SDK available for Python only. JavaScript SDK is on the roadmap.

## Support

Contact api-support@acme.io for help.
Last updated: 2024-01-15
