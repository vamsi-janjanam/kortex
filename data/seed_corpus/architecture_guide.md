# Acme Platform — System Architecture Guide

## Overview

The Acme Platform is a distributed SaaS system serving enterprise customers. This document describes the production architecture as of Q1 2025.

## Core Services

### API Gateway
All external traffic enters through the API Gateway (Kong). Responsibilities:
- JWT validation (OAuth 2.0 bearer tokens)
- Rate limiting per tenant
- Request routing to upstream services
- TLS termination

### Document Service
Manages document storage and retrieval. Stack: FastAPI + PostgreSQL + S3.
- Documents stored as S3 objects with metadata in PostgreSQL
- Full-text search via pgvector (PostgreSQL extension)
- Async processing via Celery workers

### Search Service
Hybrid search combining semantic and keyword retrieval.
- Vector store: Qdrant (self-hosted on AWS EKS)
- Embedding model: OpenAI text-embedding-3-large
- BM25 keyword index: Elasticsearch
- Reranking: Cohere Rerank API

### Auth Service
OAuth 2.0 authorization server (Keycloak).
- Issues JWT access tokens with 1-hour expiry
- Supports SAML 2.0 SSO for enterprise customers
- MFA via TOTP and WebAuthn

## Data Layer

| Store | Technology | Use Case |
|-------|-----------|---------|
| Primary DB | PostgreSQL 16 | User data, metadata, configuration |
| Cache | Redis 7 | Session cache, rate limit counters |
| Object Store | AWS S3 | Document binary storage |
| Vector Store | Qdrant | Semantic search embeddings |
| Search Index | Elasticsearch | Full-text keyword search |
| Event Stream | Apache Kafka | Async event processing |

## Deployment

- **Cloud**: AWS (us-east-1 primary, eu-west-1 DR)
- **Container orchestration**: Kubernetes (EKS)
- **CI/CD**: GitHub Actions → ECR → ArgoCD
- **Monitoring**: Datadog (metrics, logs, traces)
- **Incident management**: PagerDuty

## Security

- All data encrypted at rest (AES-256) and in transit (TLS 1.3)
- Customer data isolated per tenant (row-level security in PostgreSQL)
- SOC 2 Type II certified
- GDPR and HIPAA compliant
- Penetration testing quarterly

## SLAs

| Service | Uptime SLA | Recovery Time |
|---------|-----------|--------------|
| API Gateway | 99.99% | < 1 min |
| Document Service | 99.9% | < 5 min |
| Search Service | 99.9% | < 5 min |
| Auth Service | 99.99% | < 1 min |

## Team Ownership

| Service | Team | Oncall Rotation |
|---------|------|----------------|
| API Gateway | Platform Eng | platform-oncall |
| Document Service | Search & Storage | storage-oncall |
| Search Service | AI Platform | ai-platform-oncall |
| Auth Service | Security | security-oncall |
