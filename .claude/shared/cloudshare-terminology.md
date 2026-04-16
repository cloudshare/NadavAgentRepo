# CloudShare Core Terminology

## "Accelerate" vs "Classic"

The `experiences-backend` and `experiences-client` services are collectively referred to as **"Accelerate"** within the CloudShare organization. When a user mentions "Accelerate" it typically refers to one or more of:
- The Experiences Backend service (`experiences-backend` repo, logged in `prod-appinsights`)
- The Experiences Client frontend (`experiences-client` repo)
- Users or subscriptions that have the **Accelerate feature flag** enabled

**`isExperiencesAppUser`** is `true` when the user has at least one subscription marked as Accelerate. This flag controls which URL variants are generated and which UI the user sees.

Treat any reference to "Accelerate failures", "Accelerate users", or "Accelerate is broken" as implying these services and/or the Accelerate-flagged user population.

**Classic** users go through the CloudShare WebApp directly (AngularJS/Angular UI in the `cloudshare` repo), without passing through the Experiences Backend layer.

## Entity Name Aliases

The same entity is referred to by different names across codebases, teams, and documentation. Treat these as synonyms:

| Canonical / newer name | Alias(es) |
|------------------------|-----------|
| Team | Vendor |
| Subscription | Contract, Account (a collection of projects) |
| Blueprint | Prototype |
| ExperienceBlueprint | CourseStage |
| Project | Campaign |
| Experience | Class, Course |
| Snapshot | PrototypeVersion |
| Policy | Package |

## CI = webinteg

**CI** and **webinteg** are the same environment. It is called **CI** in the Accelerate/kubernetes-deployment context and **webinteg** everywhere else (WebApp, TeamCity, general team usage). Either name may be used interchangeably.
