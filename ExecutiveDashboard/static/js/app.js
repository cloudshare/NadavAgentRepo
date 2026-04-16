// ---------------------------------------------------------------------------
// Executive Dashboard – Dynamic Frontend
// ---------------------------------------------------------------------------

let DATA = null;
let sortState = { col: null, asc: true };

const AVATAR_COLORS = ['av-1','av-2','av-3','av-4','av-5','av-6','av-7'];

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    fetchData();
    // Auto-refresh every 5 minutes
    setInterval(() => fetchData(), 5 * 60 * 1000);

    // Modal close handlers
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('modal-overlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });

    // Sortable table headers
    document.querySelectorAll('.modal-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => handleSort(th.dataset.sort));
    });
});

// ---------------------------------------------------------------------------
// Data Fetching
// ---------------------------------------------------------------------------
async function fetchData(force = false) {
    const btn = document.getElementById('refresh-btn');
    btn.classList.add('loading');

    try {
        const url = '/api/dashboard' + (force ? '?refresh=1' : '');
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        DATA = await resp.json();
        if (DATA.error) throw new Error(DATA.error);
        render();
    } catch (err) {
        showError(err.message);
    } finally {
        btn.classList.remove('loading');
    }
}

function refreshData() {
    fetchData(true);
}

function showError(msg) {
    document.getElementById('loading-state').style.display = 'none';
    document.getElementById('main-content').style.display = 'none';
    document.getElementById('error-state').style.display = 'block';
    document.getElementById('error-message').textContent = msg;
}

// ---------------------------------------------------------------------------
// Master Render
// ---------------------------------------------------------------------------
function render() {
    document.getElementById('loading-state').style.display = 'none';
    document.getElementById('error-state').style.display = 'none';
    document.getElementById('main-content').style.display = 'block';

    renderHeader();
    renderKPI();
    renderOverallProgress();
    renderPhases();
    renderDonut();
    renderTeam();
    renderRisks();
    renderMilestones();
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------
function renderHeader() {
    const { initiative, fetchedAt } = DATA;
    document.getElementById('initiative-title').textContent = initiative.summary;
    document.getElementById('initiative-subtitle').textContent =
        `${initiative.key} \u00B7 ${initiative.project} \u00B7 Program Owner: ${initiative.owner}`;

    const badge = document.getElementById('status-badge');
    const statusText = document.getElementById('status-text');
    statusText.textContent = initiative.status;

    badge.className = 'status-badge';
    if (initiative.status.toLowerCase().includes('progress')) {
        badge.classList.add('in-progress');
    } else if (initiative.status.toLowerCase() === 'done') {
        badge.classList.add('done');
    } else {
        badge.classList.add('in-progress');
    }

    const d = new Date(fetchedAt);
    document.getElementById('last-updated').textContent =
        `Data as of ${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}, ${d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;
}

// ---------------------------------------------------------------------------
// KPI Cards
// ---------------------------------------------------------------------------
function renderKPI() {
    const { kpi, allTasks, phases } = DATA;
    const row = document.getElementById('kpi-row');
    row.innerHTML = `
        <div class="kpi-card blue" onclick="openModal('All Tasks', allTasksFilter())">
            <div class="kpi-label">Total Tasks</div>
            <div class="kpi-value">${kpi.totalTasks}</div>
            <div class="kpi-detail">Across ${kpi.phasesTotal} phases</div>
        </div>
        <div class="kpi-card green" onclick="openModal('Completed Tasks', statusFilter('done'))">
            <div class="kpi-label">Completed</div>
            <div class="kpi-value">${kpi.done}</div>
            <div class="kpi-detail">${kpi.percentDone}% of all tasks</div>
        </div>
        <div class="kpi-card yellow" onclick="openModal('In Progress Tasks', statusFilter('indeterminate'))">
            <div class="kpi-label">In Progress</div>
            <div class="kpi-value">${kpi.inProgress}</div>
            <div class="kpi-detail">Actively being worked</div>
        </div>
        <div class="kpi-card red" onclick="openModal('Not Started Tasks', statusFilter('new'))">
            <div class="kpi-label">Not Started</div>
            <div class="kpi-value">${kpi.todo}</div>
            <div class="kpi-detail">Backlog / To Do</div>
        </div>
        <div class="kpi-card purple" onclick="openModal('Phase Overview', phaseOverviewTasks())">
            <div class="kpi-label">Phases Done</div>
            <div class="kpi-value">${kpi.phasesDone} / ${kpi.phasesTotal}</div>
            <div class="kpi-detail">${phaseDoneNames()}</div>
        </div>
    `;
}

function phaseDoneNames() {
    const done = DATA.phases.filter(p => p.percentDone === 100 && p.taskCount > 0);
    if (done.length === 0) return 'None complete yet';
    return done.map(p => p.summary.split(' ')[0]).join(' & ');
}

// ---------------------------------------------------------------------------
// Overall Progress Bar
// ---------------------------------------------------------------------------
function renderOverallProgress() {
    const { kpi } = DATA;
    const total = kpi.totalTasks || 1;
    const donePct = (kpi.done / total * 100).toFixed(1);
    const ipPct = (kpi.inProgress / total * 100).toFixed(1);
    const todoPct = (kpi.todo / total * 100).toFixed(1);

    const el = document.getElementById('overall-progress');
    el.innerHTML = `
        <div class="section-title">
            <span>Overall Program Progress</span>
            <span class="progress-pct">${kpi.percentDone}%</span>
        </div>
        <div class="progress-bar-container">
            <div class="progress-segment done" style="width:${donePct}%" onclick="openModal('Completed Tasks', statusFilter('done'))"></div>
            <div class="progress-segment in-prog" style="width:${ipPct}%" onclick="openModal('In Progress Tasks', statusFilter('indeterminate'))"></div>
            <div class="progress-segment todo" style="width:${todoPct}%"></div>
        </div>
        <div class="progress-labels">
            <div class="progress-label" onclick="openModal('Completed Tasks', statusFilter('done'))"><span class="swatch done"></span> Done (${kpi.done})</div>
            <div class="progress-label" onclick="openModal('In Progress Tasks', statusFilter('indeterminate'))"><span class="swatch in-prog"></span> In Progress (${kpi.inProgress})</div>
            <div class="progress-label" onclick="openModal('Not Started Tasks', statusFilter('new'))"><span class="swatch todo"></span> To Do (${kpi.todo})</div>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// Phases
// ---------------------------------------------------------------------------
function renderPhases() {
    const el = document.getElementById('phases-panel');
    let html = '<div class="section-title">Phase Breakdown</div>';

    DATA.phases.forEach((phase, idx) => {
        const pctClass = phase.percentDone === 100 ? 'complete' :
                         phase.percentDone > 0 ? 'partial' : 'zero';
        const numClass = phase.percentDone === 100 ? 'done' :
                         phase.percentDone > 0 ? 'in-prog' : 'todo';

        const statusLower = phase.status.toLowerCase();
        let pillClass = 'backlog';
        if (statusLower === 'done') pillClass = 'done';
        else if (statusLower === 'in progress') pillClass = 'in-progress';
        else if (statusLower === 'selected for development') pillClass = 'selected';

        const tc = phase.taskCount;
        const doneW = tc ? (phase.done / tc * 100) : 0;
        const ipW = tc ? (phase.inProgress / tc * 100) : 0;

        const label = phaseLabel(idx, phase.summary);
        const meta = `${phase.taskCount} tasks \u00B7 ${phase.assignee}`;

        html += `
        <div class="phase-row" onclick="openModal('${escHtml(phase.summary)}', phaseTasks(${idx}))">
            <div class="phase-number ${numClass}">${label}</div>
            <div class="phase-info">
                <div class="phase-name">${escHtml(phase.summary)}</div>
                <div class="phase-meta">${meta}</div>
            </div>
            <div class="phase-bar-wrap">
                <div class="phase-bar">
                    <div class="done" style="width:${doneW}%"></div>
                    <div class="in-prog" style="width:${ipW}%"></div>
                </div>
            </div>
            <div class="phase-pct ${pctClass}">${phase.percentDone}%</div>
            <div class="phase-status-pill ${pillClass}">${escHtml(phase.status)}</div>
        </div>`;
    });

    el.innerHTML = html;
}

function phaseLabel(idx, summary) {
    // Try to extract a phase number from summary, fallback to index
    const m = summary.match(/phase\s*([\d.]+)/i);
    if (m) return m[1];
    return idx;
}

// ---------------------------------------------------------------------------
// Donut Chart
// ---------------------------------------------------------------------------
function renderDonut() {
    const { kpi } = DATA;
    const total = kpi.totalTasks || 1;
    const r = 54;
    const circ = 2 * Math.PI * r;

    const doneArc = (kpi.done / total) * circ;
    const ipArc = (kpi.inProgress / total) * circ;
    const todoArc = (kpi.todo / total) * circ;

    const el = document.getElementById('donut-panel');
    el.innerHTML = `
        <div class="section-title">Task Distribution</div>
        <div class="donut-wrap">
            <div class="donut-chart">
                <svg width="140" height="140" viewBox="0 0 140 140">
                    <circle cx="70" cy="70" r="${r}" fill="none" stroke="#238636" stroke-width="16"
                        stroke-dasharray="${doneArc} ${circ}" stroke-dashoffset="0"
                        onclick="openModal('Completed Tasks', statusFilter('done'))" />
                    <circle cx="70" cy="70" r="${r}" fill="none" stroke="#d29922" stroke-width="16"
                        stroke-dasharray="${ipArc} ${circ}" stroke-dashoffset="${-doneArc}"
                        onclick="openModal('In Progress Tasks', statusFilter('indeterminate'))" />
                    <circle cx="70" cy="70" r="${r}" fill="none" stroke="#484f58" stroke-width="16"
                        stroke-dasharray="${todoArc} ${circ}" stroke-dashoffset="${-(doneArc + ipArc)}"
                        onclick="openModal('Not Started Tasks', statusFilter('new'))" />
                </svg>
                <div class="donut-center">
                    <div class="num">${kpi.totalTasks}</div>
                    <div class="label">Total</div>
                </div>
            </div>
            <div class="donut-legend">
                <div class="legend-item" onclick="openModal('Completed Tasks', statusFilter('done'))">
                    <span class="legend-dot" style="background:#238636"></span>
                    Done
                    <span class="legend-count">${kpi.done}</span>
                </div>
                <div class="legend-item" onclick="openModal('In Progress Tasks', statusFilter('indeterminate'))">
                    <span class="legend-dot" style="background:#d29922"></span>
                    In Progress
                    <span class="legend-count">${kpi.inProgress}</span>
                </div>
                <div class="legend-item" onclick="openModal('Not Started Tasks', statusFilter('new'))">
                    <span class="legend-dot" style="background:#484f58"></span>
                    To Do
                    <span class="legend-count">${kpi.todo}</span>
                </div>
            </div>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// Team Workload
// ---------------------------------------------------------------------------
function renderTeam() {
    const el = document.getElementById('team-panel');
    let html = '<div class="section-title">Team Workload</div>';

    DATA.team.forEach((member, idx) => {
        const initials = member.name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
        const avClass = AVATAR_COLORS[idx % AVATAR_COLORS.length];
        const safeName = escAttr(member.name);

        let counts = '';
        if (member.done) counts += `<span class="task-count done">${member.done}</span>`;
        if (member.inProgress) counts += `<span class="task-count active">${member.inProgress}</span>`;
        if (member.todo) counts += `<span class="task-count pending">${member.todo}</span>`;

        html += `
        <div class="team-member" onclick="openModal('${safeName}', teamTasks('${safeName}'))">
            <div class="avatar ${avClass}">${initials}</div>
            <div class="team-name">${escHtml(member.name)}</div>
            <div class="team-tasks">${counts}</div>
        </div>`;
    });

    el.innerHTML = html;
}

// ---------------------------------------------------------------------------
// Risks
// ---------------------------------------------------------------------------
function renderRisks() {
    const risks = computeRisks();
    const el = document.getElementById('risks-panel');
    let html = '<div class="section-title">Risks & Attention Items</div>';

    risks.forEach(risk => {
        const icon = risk.level === 'high' ? '&#9888;' :
                     risk.level === 'medium' ? '&#9679;' : '&#9432;';
        const levelLabel = risk.level === 'high' ? 'High Risk' :
                           risk.level === 'medium' ? 'Medium Risk' : 'Note';

        html += `
        <div class="risk-item" onclick="openModal('${escAttr(risk.title)}', ${risk.filterExpr})">
            <div class="risk-icon ${risk.level}">${icon}</div>
            <div class="risk-text">
                <div class="risk-label ${risk.level}">${levelLabel}</div>
                <strong>${escHtml(risk.title)}</strong> &mdash; ${escHtml(risk.detail)}
            </div>
        </div>`;
    });

    el.innerHTML = html;
}

function computeRisks() {
    const risks = [];
    const { phases, allTasks } = DATA;

    // Zero-progress phases with tasks
    const zeroPhasesWithTasks = phases.filter(p => p.percentDone === 0 && p.taskCount > 0);
    if (zeroPhasesWithTasks.length > 0) {
        const names = zeroPhasesWithTasks.map(p => p.summary).join(', ');
        risks.push({
            level: 'high',
            title: `${zeroPhasesWithTasks.length} phase(s) have zero progress`,
            detail: `${names}. Planning should start before active phases complete.`,
            filterExpr: `zeroProgressPhaseTasks()`,
        });
    }

    // Unassigned tasks
    const unassigned = allTasks.filter(t => t.assignee === 'Unassigned');
    if (unassigned.length > 0) {
        risks.push({
            level: 'high',
            title: `${unassigned.length} tasks are unassigned`,
            detail: 'Resource allocation needed to avoid bottlenecks.',
            filterExpr: `unassignedTasks()`,
        });
    }

    // Largest bottleneck phase (most remaining, >50% remaining)
    const active = phases.filter(p => p.percentDone > 0 && p.percentDone < 100);
    if (active.length > 0) {
        const bottleneck = active.reduce((a, b) => (b.taskCount - b.done) > (a.taskCount - a.done) ? b : a);
        const remaining = bottleneck.taskCount - bottleneck.done;
        if (remaining >= 5) {
            const bIdx = phases.indexOf(bottleneck);
            risks.push({
                level: 'medium',
                title: `${bottleneck.summary} is at ${bottleneck.percentDone}% with ${remaining} tasks remaining`,
                detail: 'Largest active workload. May need additional resources.',
                filterExpr: `phaseTasks(${bIdx})`,
            });
        }
    }

    // Empty phases (no tasks at all)
    const empty = phases.filter(p => p.taskCount === 0);
    if (empty.length > 0) {
        const names = empty.map(p => p.summary).join(', ');
        risks.push({
            level: 'medium',
            title: `${empty.length} phase(s) have no child tasks`,
            detail: `${names}. Scope and effort TBD.`,
            filterExpr: `allTasksFilter()`,
        });
    }

    // Missing due dates
    const noDue = phases.filter(p => !p.dueDate);
    if (noDue.length === phases.length && phases.length > 0) {
        risks.push({
            level: 'info',
            title: 'No due dates set on any phase',
            detail: 'Consider adding milestones for tracking against timeline.',
            filterExpr: `allTasksFilter()`,
        });
    } else if (noDue.length > 0) {
        risks.push({
            level: 'info',
            title: `${noDue.length} phase(s) missing due dates`,
            detail: 'Consider adding target completion dates for better tracking.',
            filterExpr: `allTasksFilter()`,
        });
    }

    return risks;
}

// ---------------------------------------------------------------------------
// Milestones
// ---------------------------------------------------------------------------
function renderMilestones() {
    const milestones = computeMilestones();
    const el = document.getElementById('milestones-panel');
    let html = '<div class="section-title">Key Milestones</div>';

    milestones.forEach(ms => {
        const checkClass = ms.done ? 'done' : 'pending';
        const textClass = ms.done ? 'done' : 'pending';
        const icon = ms.done ? '&#10003;' : '&#9675;';

        html += `
        <div class="milestone-item" onclick="openModal('${escAttr(ms.phase)}', phaseTasks(${ms.phaseIdx}))">
            <div class="milestone-check ${checkClass}">${icon}</div>
            <div class="milestone-text ${textClass}">${escHtml(ms.label)}</div>
        </div>`;
    });

    el.innerHTML = html;
}

function computeMilestones() {
    const { phases } = DATA;
    const milestones = [];

    const milestoneMap = [
        { keywords: ['poc', 'validation'], label: 'POC validation complete' },
        { keywords: ['foundation', 'planning', 'networking', 'sso', 'organization'], label: 'AWS Foundation & Networking deployed' },
        { keywords: ['infrastructure', 'terraform', 'iac'], label: 'Infrastructure as Code modules complete' },
        { keywords: ['monitoring', 'log'], label: 'Monitoring & alerting fully operational' },
        { keywords: ['database', 'migration', 'rds'], label: 'Database migration to RDS complete' },
        { keywords: ['modernization', 'ci/cd', 'pipeline', 'containeriz'], label: 'App modernization & CI/CD pipelines deployed' },
        { keywords: ['integ'], label: 'Integ environment migrated to AWS' },
        { keywords: ['cutover', 'full migration', 'testing'], label: 'Production cutover executed' },
        { keywords: ['optimization', 'decommission'], label: 'Legacy infrastructure decommissioned' },
    ];

    phases.forEach((phase, idx) => {
        const lower = phase.summary.toLowerCase();
        const mapped = milestoneMap.find(m => m.keywords.some(k => lower.includes(k)));
        milestones.push({
            label: mapped ? mapped.label : `${phase.summary} complete`,
            done: phase.percentDone === 100 && phase.taskCount > 0,
            phase: phase.summary,
            phaseIdx: idx,
        });
    });

    return milestones;
}

// ---------------------------------------------------------------------------
// Filter Functions (used by onclick handlers)
// ---------------------------------------------------------------------------
function allTasksFilter() { return DATA.allTasks; }
function statusFilter(cat) { return DATA.allTasks.filter(t => t.statusCategory === cat); }
function phaseTasks(idx) { return DATA.phases[idx] ? DATA.phases[idx].tasks : []; }
function teamTasks(name) { return DATA.allTasks.filter(t => t.assignee === name); }
function unassignedTasks() { return DATA.allTasks.filter(t => t.assignee === 'Unassigned'); }
function zeroProgressPhaseTasks() {
    const tasks = [];
    DATA.phases.forEach(p => { if (p.percentDone === 0 && p.taskCount > 0) tasks.push(...p.tasks); });
    return tasks;
}
function phaseOverviewTasks() {
    // Show tasks from the most interesting phases (incomplete ones)
    const tasks = [];
    DATA.phases.forEach(p => tasks.push(...p.tasks));
    return tasks;
}

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------
let currentModalTasks = [];

function openModal(title, tasks) {
    currentModalTasks = tasks || [];
    sortState = { col: null, asc: true };
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-count').textContent = `${currentModalTasks.length} tasks`;
    renderModalTable(currentModalTasks);
    document.getElementById('modal-overlay').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
    document.body.style.overflow = '';
}

function renderModalTable(tasks) {
    const tbody = document.getElementById('modal-tbody');
    if (tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:#484f58;">No tasks found</td></tr>';
        return;
    }

    tbody.innerHTML = tasks.map(t => {
        const statusCls = t.statusCategory === 'done' ? 'done' :
                          t.statusCategory === 'indeterminate' ? 'in-progress' : 'todo';
        const priCls = (t.priority || '').toLowerCase();
        const updated = t.updated ? new Date(t.updated).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';

        return `<tr>
            <td><a class="key-link" href="${escAttr(t.webUrl)}" target="_blank" rel="noopener">${escHtml(t.key)}</a></td>
            <td>${escHtml(t.summary)}</td>
            <td><span class="status-pill ${statusCls}">${escHtml(t.status)}</span></td>
            <td>${escHtml(t.assignee)}</td>
            <td><span class="priority-pill ${priCls}">${escHtml(t.priority)}</span></td>
            <td>${updated}</td>
        </tr>`;
    }).join('');
}

function handleSort(col) {
    if (sortState.col === col) {
        sortState.asc = !sortState.asc;
    } else {
        sortState.col = col;
        sortState.asc = true;
    }

    // Update arrow indicators
    document.querySelectorAll('.modal-table th[data-sort]').forEach(th => {
        const arrow = th.querySelector('.sort-arrow');
        if (th.dataset.sort === col) {
            arrow.textContent = sortState.asc ? '\u25B2' : '\u25BC';
        } else {
            arrow.textContent = '';
        }
    });

    const sorted = [...currentModalTasks].sort((a, b) => {
        let va = (a[col] || '').toString().toLowerCase();
        let vb = (b[col] || '').toString().toLowerCase();
        if (col === 'updated') {
            va = a.updated || '';
            vb = b.updated || '';
        }
        if (va < vb) return sortState.asc ? -1 : 1;
        if (va > vb) return sortState.asc ? 1 : -1;
        return 0;
    });

    renderModalTable(sorted);
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function escHtml(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function escAttr(str) {
    return escHtml(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
