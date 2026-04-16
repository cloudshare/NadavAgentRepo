# CloudShare Azure Deployment & Infrastructure

> For service topology and request routing, see `.claude/shared/service-relations.md`.
> For WebApp ↔ Experiences Service sync, see `.claude/shared/entity-change-mechanism.md`.

## Hosting & Infrastructure

| Component | Hosting | Resource Group / Location |
|-----------|---------|--------------------------|
| **WebApp / API v3** (`cloudshare` repo) | **On-premises** (IIS on Windows Server) | On-prem data center |
| **Accelerate** (`experiences-backend`, `experiences-client`) | **Azure Kubernetes Service** — `prod-env-cluster` | `production-environment-kubernetes` |

- All Accelerate cloud infrastructure lives in the **`production-environment-kubernetes`** resource group, `CloudShare Production Services on Azure` subscription.
- The WebApp runs fully on-prem — not in Azure. App Insights telemetry is shipped via SDK to `classic-appinsights-prod`.

### Deployment

| Component | CI/CD | Mechanism |
|-----------|-------|-----------|
| **WebApp** | TeamCity | Deploy to IIS (on-prem) |
| **Accelerate services** | TeamCity | `kubectl rollout update` → AKS `prod-env-cluster` |

Container images are stored in **`cloudshareregistry.azurecr.io`** (Azure Container Registry). All pods pull images using the `cloudshare-registry-pull` secret.

The Kubernetes configuration is managed in the **`kubernetes-deployment`** repo (local path: `c:\Repos\kubernetes-deployment`) using **Kustomize** with a base + per-environment overlays.

---

## Databases

| Service | Database | Type | Details |
|---------|----------|------|---------|
| **WebApp / API v3** | CloudShare main DB | **On-premises MS SQL Server** (managed) | On-prem, same data center as WebApp |
| **Experiences Service** | `Experiences` | **Azure SQL** | Instance: `cloudshare-prod` |
| **Client Configuration Service** | `ClientConfiguration` | **Azure SQL** | Instance: `cloudshare-prod` |
| **CI environment only** | Local SQL Server | Containerized SQL Server 2022 with FTS | Image: `cloudshareregistry.azurecr.io/sqlserver-fts:2022-latest`; 8Gi Azure Disk PVC; not present in preprod/production |

---

## Configuration

For runtime configuration detail — DynamicConfig / `dynamic_web_config.xml`, file locations, how to add fields, AKS config cascade, Key Vault names — see **`.claude/shared/dynamic-config.md`**.
