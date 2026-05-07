# API Contract

## Contract Version

Current version: `v1`

This document defines how the model platform communicates with the agent service.

---

## 1. Platform → Agent: Drift Webhook

### Endpoint

```http
POST /webhooks/drift

POST /webhooks/drift request body
POST /webhooks/drift response body
POST /registry/promote request body
POST /registry/promote response body
versioning rule
breaking-change policy
