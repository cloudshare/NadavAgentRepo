---
name: cs-setup-new-pc
description: >
  Set up Claude Code from scratch on a new Windows PC for CloudShare development,
  including prerequisites, MCP servers (Azure, Atlassian), plugins (GitHub, Figma, etc.),
  and OAuth authentication. WHEN: new PC setup, onboarding a developer, reinstalling
  Claude Code, "set up Claude Code", "configure MCP servers", "fresh install", "new machine".
---

# CloudShare Claude Code — New PC Setup

Walk the user through each section in order. Check off each step as you confirm it's done.

---

## 1. Install Claude Code

```bash
winget install Anthropic.ClaudeCode
```

Then log in:
```bash
claude login
```

---

## 2. Install Prerequisites

### Azure MCP (`azmcp`)

```bash
npm install -g @azure/mcp
```

Verify: `azmcp --version`

---

## 3. Configure MCP Servers

### 4a. Azure MCP (user-scope)

```bash
claude mcp add --scope user --transport stdio azure -- azmcp server start
```

Resulting config in `~/.claude.json`:
```json
"azure": {
  "type": "stdio",
  "command": "azmcp",
  "args": ["server", "start"],
  "env": {}
}
```

### 4b. Atlassian MCP (cloudshare project-scope)

Run this from inside `C:\Repos\cloudshare` (or any subdirectory):
```bash
claude mcp add --scope project --transport http atlassian https://mcp.atlassian.com/v1/mcp
```

This writes the server into the project's local config so it's available whenever you open the cloudshare repo.

---

## 4. Enable Plugins

Open `~/.claude/settings.json` (create it if it doesn't exist) and add:

```json
{
  "enabledPlugins": {
    "github@claude-plugins-official": true,
    "code-review@claude-plugins-official": true,
    "skill-creator@claude-plugins-official": true,
    "claude-code-setup@claude-plugins-official": true,
    "atlassian@claude-plugins-official": true,
    "figma@claude-plugins-official": true
  }
}
```

### GitHub plugin

Bundles its own MCP server — no Docker required. Needs a Personal Access Token. Create one at **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens** with:
- Repository access: All repositories (or select the ones you need)
- Permissions: Contents (read), Issues (read/write), Pull requests (read/write), Metadata (read)

Set it as an environment variable so the plugin can pick it up:
```bash
# Add to Windows environment variables (System Properties → Environment Variables)
GITHUB_PERSONAL_ACCESS_TOKEN=<your-pat>
```

### Figma plugin

Bundles its own MCP server (`plugin:figma:figma`) that connects automatically — no separate token or MCP configuration needed. Just having `figma@claude-plugins-official: true` is enough.

---

## 5. Authenticate Atlassian

After starting Claude Code in the cloudshare directory, run:

```
/mcp
```

Select **Atlassian** and complete the OAuth browser flow.

---

## 6. Verify Everything

Run `/mcp` and confirm all servers show **✓ Connected**:

| Server | Expected status |
|--------|----------------|
| github (via plugin) | ✓ Connected |
| azure | ✓ Connected |
| atlassian | ✓ Connected |

If any server shows an error, the most common fixes are:
- **github** — ensure `github@claude-plugins-official` is enabled in `settings.json` and `GITHUB_PERSONAL_ACCESS_TOKEN` is set in your environment
- **azure** — `azmcp` not on PATH; run `npm install -g @azure/mcp` again
- **atlassian** — re-run the OAuth flow via `/mcp`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `azmcp: command not found` | `npm install -g @azure/mcp`, then restart your terminal |
| Atlassian MCP shows old auth | `claude mcp remove atlassian`, re-add, re-authenticate |

---

## Done!

Ask the user: **"Did you run into any issues or steps that weren't covered above?"**

If they describe anything — a missing prerequisite, a workaround they needed, a confusing step, a gotcha — update this skill file immediately to capture it. Add it to the relevant section, or to Troubleshooting if it's a specific error/fix pair. Don't ask for permission, just do it and tell them what you added.
