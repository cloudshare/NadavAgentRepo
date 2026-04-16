# CloudShare Runtime Configuration

## WebApp (on-prem): DynamicConfig

The WebApp reads runtime configuration from **`dynamic_web_config.xml`** via the `DynamicConfig` class (`src/Itst.Config/DynamicConfig.cs`). This file is reloaded at runtime without a redeploy — any code reading it via `ServiceLocator<IDynamicXmlLoader<DynamicConfig>>.Service.Config` picks up changes immediately.

### File locations

| Purpose | Path |
|---------|------|
| Local dev defaults | `cloudshare/local_config/dynamic_web_config.xml` |
| Per-environment overrides | `cloudshare-secrets/local_config/UpdateXml/web/dynamic_web_config.xml` |

The secrets file uses XPath-targeted replacements keyed by server name regex:

```xml
<location xpath="/Config/ApplicationInsights">
    <server name="^integ$|^integ2$">
        <replace>
            <ApplicationInsights ... />
        </replace>
    </server>
    <server name="^prod$">
        <replace>
            <ApplicationInsights ... />
        </replace>
    </server>
    <server name=".*"/>   <!-- fallback: leave as-is -->
</location>
```

### Adding a new config field

1. Add a property to the relevant inner config class in `DynamicConfig.cs` with `[XmlAttribute("camelCaseName")]`. Do **not** set a C# default value — the XML is the source of truth.
2. Add the attribute with its default value to `cloudshare/local_config/dynamic_web_config.xml`.
3. Add the attribute to both `^integ$|^integ2$` and `^prod$` blocks in `cloudshare-secrets/local_config/UpdateXml/web/dynamic_web_config.xml`.

### Notable config sections

| Section | Class | Purpose |
|---------|-------|---------|
| `ApplicationInsights` | `ApplicationInsightsConfig` | Connection string, sampling, telemetry filters |
| `Features` | `FeaturesConfig` | Feature flags |
| `Redis` | `RedisConfig` | Redis connection |
| `EntityChanges` | `EntityChangesConfig` | Service Bus entity sync |
| `Heartbeats` | `HeartbeatsConfig` | Heartbeat intervals |
| `General` | `GeneralConfig` | Misc runtime toggles |

### ApplicationInsights

Fields are defined in `ApplicationInsightsConfig` inside `DynamicConfig.cs`. The three `filter*` flags (`filterSuccessfulSqlDependencies`, `filterPollingRequests`, `filterIdleServiceBusDependencies`) are implemented as `ITelemetryProcessor` classes in `src/Itst.Web.App/Code/AppInsights/` and registered in `src/Itst.Web.App/ApplicationInsights.config`.

---

## Accelerate Services (AKS): Config Cascade

Configuration for services in the `production-environment-kubernetes` resource group is resolved in this order (later sources win):

1. **`appsettings.json`** — baked into the container image at build time
2. **Kubernetes ConfigMap** — environment-specific values mounted at `/app/config` (per-service) and `/app/config/global` (global)
3. **Azure Key Vault** (via Secret Store CSI driver) — secrets mounted at `/app/secrets`

Key Vault names per environment:

| Environment | Key Vault |
|-------------|-----------|
| CI / webinteg | `CIEnvKeyVault` |
| Preprod | `preprodKubernetes` |
| Production | `prod-kubernetes-keyvault` |

Secrets in Key Vault include: SQL password, Application Insights connection string, Service Bus connection strings, JWT signing/encrypting keys, BFF cookie decryption key.

The `ASPNETCORE_ENVIRONMENT` / `DOTNET_ENVIRONMENT` values per environment: `CI`, `Preprod`, `Production`, `LocalKube` (local dev).

Kubernetes configuration (ConfigMaps, resource limits, health checks) is managed in the **`kubernetes-deployment`** repo (`c:\Repos\kubernetes-deployment`) using Kustomize with a base + per-environment overlays.
