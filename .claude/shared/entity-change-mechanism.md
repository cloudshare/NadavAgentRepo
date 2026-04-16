# EntityChange Mechanism

Synchronization system that propagates data changes from the CloudShare WebApp (on-prem, `cloudshare` repo) to the Experiences Service (AKS, `experiences-backend` repo) via Azure Service Bus.

When a domain object is persisted in the WebApp's SQL Server, the change is published to a Service Bus topic per entity type. The Experiences Service consumes those messages and updates its own `Experiences` Azure SQL database accordingly.

---

## Publisher side (`cloudshare` repo)

### 1. Detection — NHibernate interceptor

`ServicesEntityChangeDomainObjectInterceptor` (`src/Itst.NHib.Repos/NHibInterceptor/`) is an NHibernate `EmptyInterceptor` hooked into `OnPostInsert`, `OnPostUpdate`, `OnPostDelete`, and `OnPostUpdateCollection` (only for `Contract`).

For updates it diffs old vs new state. Only changes to properties registered in `ServicesEntityChangeNotificationConfig` trigger a notification. Entities are accumulated per-session during the transaction, then flushed in `AfterTransactionCompletion` (or `OnFlush`).

### 2. Watched entities — `ServicesEntityChangeNotificationConfig`

`src/Itst.NHib.Repos/NHibInterceptor/ServicesEntityChangeNotificationConfig.cs` lists ~25 domain types and the specific properties to watch. Adding a new entity requires a registration here **and** an `EntityType` defined on the domain object.

Key entity type codes: `RE`=Region, `PR`=Project, `BP`=Blueprint, `PP`=ProjectPrototype, `CO`=Course/Experience, `SG`=CourseStage/ExperienceBlueprint, `SD`=Student, `CI`=Instructor, `US`=User, `TM`=Team/Vendor, `EN`=Environment, `CN`=Contract/Subscription, `PO`=RoleBasedPermission, `TS`=TrainingSettings, `TF`/`FV`=CustomFieldDefinition/Value, `VP`/`EU`=VendorUserProject/EnterpriseUserProject, `DT`=UserProjectDefaultTeam, `ES`=UserEnvStudent, `CA`/`PA`=CourseEndUsersAccessPermission/ProjectEndUsersAccessPermission, `NB`=NonBusinessEmailDomain, `PG`=ProjectFlags.

### 3. Message format — `ChangedEntityInfo`

```json
{
  "MessageId": "guid",
  "Timestamp": "2026-03-28T12:00:00",
  "EntityType": "BP",
  "EntityId": 12345,
  "Operation": "Update",
  "Originator": "user@example.com",
  "ChangedProperties": { "FriendlyNameId": "New Name", "ValidUntil": "2027-01-01" }
}
```

`ChangedProperties` contains **only the properties that changed** (new values). Domain-typed properties serialized as `{PropertyName}Id`, collections as `{PropertyName}Ids`.

### 4. Sending — `ServiceEntityChangeSender`

`src/Itst.NHib.Repos/NHibInterceptor/ServiceEntityChangeSender.cs` — groups by `EntityType`, resolves topic via `ITopicHelper.GetTopic(entityType)`, sends JSON batches to Service Bus. Config: `DynamicConfig.EntityChanges.ServiceBusPrimaryConnectionString`, `EntityChanges.PublishToServices` flag must be `true`, `EntityChanges.Suffix` for environment isolation.

---

## Consumer side (`experiences-backend` repo)

### SyncWorker

`Experiences.Service/Experiences.Service/Workers/SyncWorker.cs` — `BackgroundService` that creates topics if needed, starts one `EntityChangeConsumer<TInfo, THandler>` per entity type, runs until cancellation.

Entity types consumed: `BP, CO, TF, FV, PR, SD, CI, US, TM, PO, EN, ES, RE, SG, TS, VP, PA, CA, NB, PG, DT`

### Handlers

Each `IEntityChangeHandler<T>` (in `Experiences.BL/Handlers/`) handles Add, Update, Delete. Add/Update checks if the record exists and compares `LastUpdatedDate` against message `Timestamp` (idempotency guard — skips if stored date is newer). Delete is soft-delete.

### Two Service Bus channels

| Config key | `ServiceName` | Purpose |
|---|---|---|
| `EntityChangedServiceBusOptions` | `ExperiencesService` | Main entity sync (all entities above) |
| `AuthEntityChangedServiceBusOptions` | `AuthService_ExperiencesService` | Auth/authorization entity changes (handled by `CS.Auth.Library`) |

The Auth channel is a **parallel subscription** to the same topics — the WebApp publishes once; both consumers receive the same messages. See `accelerate-auth.md` for the auth architecture.

---

## Configuration — Experiences.Service appsettings

Key settings in `EntityChangedServiceBusOptions`: `EnableConsumers` (master on/off), `ServiceBusConnectionString` (null in source — injected from Key Vault), `UseSuffix`/`Suffix` (topic name isolation), `NumberOfThreads` (concurrent processing per topic).

Service Bus connection strings are `null` in all source appsettings files and injected at runtime from Key Vault (see `dynamic-config.md` for Key Vault names per environment).

---

## Data flow summary

```
WebApp DB write
  → NHibernate PostInsert/PostUpdate/PostDelete
  → ServicesEntityChangeDomainObjectInterceptor (checks config, diffs properties)
  → per-session change list → AfterTransactionCompletion / OnFlush
  → ServiceEntityChangeSender.Send() → Azure Service Bus topic (per EntityType)
  → EntityChangeConsumer<TInfo, THandler> [Experiences Service]
  → IEntityChangeHandler<T>.HandleAdd/Update/DeleteOperationAsync()
  → Upsert / soft-delete in Experiences Azure SQL DB
```

---

## Resync

`ResyncAccelerateEntitiesBLService` (`src/Itst.BL/BLServices/Management Operations/Service/`) exists on the WebApp side for manual full resync when the Experiences DB gets out of sync.
