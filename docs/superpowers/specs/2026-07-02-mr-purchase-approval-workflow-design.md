# Design — MR Purchase Approval Workflow + Notifications

- **Date:** 2026-07-02
- **App:** `stock_ops` (branch `new-develop`)
- **Status:** Approved (design), pending implementation plan

## Goal

Add a **line-manager approval workflow** for Material Request of type **Purchase**, plus
**notifications** across the approval loop, that:

1. Auto-installs with the app (workflow + notifications created on `after_install`/`after_migrate`, idempotent).
2. Is **workflow-driven like the HRMS PWA** — the app reads the available transitions for a
   document+user from the server (`frappe.model.workflow.get_transitions`) and applies them via
   `apply_workflow`. Whatever an admin configures in the Desk Workflow is exactly what the app renders
   and enforces. No hard-coded action names in the client.
3. Surfaces in both the **PWA** and the **Flutter** app (an "Approvals" inbox + dynamic action buttons +
   status badges).

## Locked decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Approval mechanism | **Native ERPNext Workflow on Material Request** — gates submission for Purchase MRs; other types submit directly via a conditional transition. |
| Approver | The requesting employee's **`leave_approver`** (`requester user → Employee.user_id → leave_approver`). |
| No approver configured | **Block** the submit-for-approval with a clear message (forces HR setup). |
| In-app UX | **Approvals inbox + Approve/Reject in-app**, workflow-driven (dynamic transitions), plus status badges. |
| Notifications | **Full loop**: pending→line manager; approved→Purchase Manager; approved/rejected→requester. |
| Rejection | **Back to editable Draft** (requester revises & resubmits via a "Reopen" transition). |
| Desk parity | The same Workflow governs Desk/web-form submissions too (inherent to Workflows) — desired. |

## Scope

Only **Material Request where `material_request_type == 'Purchase'`** is gated. All other app writes are
unchanged: Transfer MRs, all Stock Entry, Purchase Receipt / Goods Return, Stock Reconciliation.

## Architecture

### 1. Custom fields (via `setup/install.py` `CUSTOM_FIELDS`, idempotent)

On **Material Request**:
- `stock_ops_approver` — Link → User, read-only, `no_copy`, hidden-ish. The resolved line manager.
- `stock_ops_approval_note` — Small Text, read-only. Reject/approve note captured from the app.

`workflow_state` (Link → Workflow State) is auto-added by Frappe when the Workflow is created.

### 2. Workflow `Stock Ops MR Approval` (auto-created on install)

Bound to **Material Request**. States (with docstatus + `allow_edit` role):

| State | docstatus | allow_edit |
|---|---|---|
| Draft | 0 | Stock Ops User |
| Pending Approval | 0 | Stock Ops Manager |
| Approved | 1 | — |
| Rejected | 0 | Stock Ops User |

Transitions (each with `condition` eval + `allowed` role):

| From | Action | To | Condition | Allowed |
|---|---|---|---|---|
| Draft | Submit for Approval | Pending Approval | `doc.material_request_type == 'Purchase'` | Stock Ops User |
| Draft | Submit | Approved | `doc.material_request_type != 'Purchase'` | Stock Ops User |
| Pending Approval | Approve | Approved | `doc.stock_ops_approver == frappe.session.user` | Employee* |
| Pending Approval | Reject | Rejected | `doc.stock_ops_approver == frappe.session.user` | Employee* |
| Rejected | Reopen | Draft | — | Stock Ops User |

\* The `allowed` role is a coarse gate set to **Employee** (which line managers have) so the approver can
also act in the **Desk web form**, matching HRMS-style Desk/app parity; the **condition**
(`stock_ops_approver == session.user`) is the real per-document gate. The approve/reject API additionally
verifies the caller is the assigned approver (or Stock Ops Manager / Purchase Manager) and applies the
transition server-side, so app approvers need no broad MR permissions. Because a Workflow binds to the
whole doctype, the conditional `Submit` / `Submit for Approval` split is what lets Transfer and other MR
types flow straight through unchanged.

### 3. Approver resolution (`stock_ops/approval.py`)

`resolve_approver(user)`:
1. `emp = Employee where user_id == user`
2. `approver = emp.leave_approver`
3. if missing → **raise** `frappe.ValidationError("Setel Leave Approver Anda di Employee dulu untuk mengajukan permintaan pembelian.")`

Called when a Purchase MR is created/updated (populates `stock_ops_approver`), and re-validated at the
"Submit for Approval" step (block if still unresolved). Draft saving is allowed; only submit-for-approval
is blocked.

### 4. Workflow-driven submit path (the one existing-behavior change)

`submit_transaction(doctype, name)` in `api.py` becomes workflow-aware:
- If the doctype has an **active Workflow** → do **not** `doc.submit()`. Instead fetch the transitions
  available to the current user (`frappe.model.workflow.get_transitions(doc)`) and apply the single
  forward transition (`apply_workflow(doc, action)`). For our workflow, exactly one transition is valid
  from Draft per the type condition: Purchase → "Submit for Approval" (→ Pending, still docstatus 0),
  others → "Submit" (→ Approved, docstatus 1).
- If no active workflow (Stock Entry / Purchase Receipt / Stock Reconciliation) → `doc.submit()` as today.

This keeps the client oblivious to action names — it just calls `submit_transaction`, and the server does
whatever the workflow says.

### 5. Workflow API for the app (HRMS-style, generic)

- `get_workflow_transitions(doctype, name)` → wraps `frappe.model.workflow.get_transitions(doc)`;
  returns `[{action, next_state}]` allowed for the current user+doc — this is exactly what the Desk uses.
- `apply_workflow_action(doctype, name, action, note=None)` → verifies caller is the assigned approver
  (or Stock Ops Manager / Purchase Manager), stores `note` into `stock_ops_approval_note`, then
  `apply_workflow(doc, action)`; returns the new `workflow_state` + docstatus.
- `list_pending_approvals(limit=50)` → Material Requests where `stock_ops_approver == frappe.session.user`
  and `workflow_state == 'Pending Approval'` (fields: name, transaction_date, material_request_type,
  owner, item count, company).
- `get_bootstrap` adds: `is_approver` (bool — the user is some employee's leave_approver OR has pending
  items) and `pending_approvals` (count) so the app shows the "Persetujuan" entry only when relevant.

### 6. Notifications (ERPNext `Notification` records, auto-created on install)

Admin-editable, standard, Email + System Notification channels (System Notification → Notification Log →
the app's existing bell/`get_notifications` polling picks it up):

| # | Event | Condition | Recipient | Channels |
|---|---|---|---|---|
| N1 | Value Change (`workflow_state`) | `== 'Pending Approval' and material_request_type == 'Purchase'` | Document field `stock_ops_approver` | Email + System |
| N2 | Submit | `material_request_type == 'Purchase'` | Role **Purchase Manager** | Email + System |
| N3 | Value Change (`workflow_state`) | `in ('Approved','Rejected') and type == 'Purchase'` | Document field `owner` (requester) | System (+ Email on Rejected) |

The existing `push.notify_doc_submit` web-push stays as-is (fires on final submit). If "Receiver by
Document Field = owner" proves unsupported, N3 falls back to a code notify in `apply_workflow_action`.

### 7. Auto-install (`setup/install.py`, idempotent)

`after_install` + `after_migrate` additionally call `setup_approval_workflow()`:
- ensure custom fields (existing `setup_custom_fields`, extended).
- upsert the Workflow + Workflow States + Workflow Document States/Transitions (delete+recreate child
  rows or match by action to stay idempotent; guarded so re-runs don't duplicate).
- upsert the three Notification records (match by a fixed `name`).
- Guard: only create if the `Purchase Manager` role exists (i.e. erpnext buying present). Workflow only
  meaningfully activates where employees/leave approvers exist (matches block-until-configured).

### 8. PWA changes (`frontend/`)

- `lib/service.js`: `listPendingApprovals`, `getWorkflowTransitions`, `applyWorkflowAction`.
- New `views/ApprovalsView.vue` (route `/approvals`): list from `listPendingApprovals`; each row opens a
  sheet showing item summary + **dynamic action buttons from `getWorkflowTransitions`** (+ optional note)
  → `applyWorkflowAction`. Menu gating key `approvals` (shown when `is_approver`).
- Home/nav: a "Persetujuan" entry with a pending-count badge (from bootstrap `pending_approvals`).
- `DocDetailView` / `DocListView`: show `workflow_state` badge for Material Request (Menunggu Persetujuan
  / Disetujui / Ditolak); the create→submit toast reads "diajukan untuk persetujuan" for Purchase.
- i18n `approval.*` (id + en). Rebuild the committed bundle.

### 9. Flutter changes (`D:\Workspace\stockops_flutter`, not in git)

- `api/erp.dart`: `listPendingApprovals`, `getWorkflowTransitions`, `applyWorkflowAction`.
- `state/app_state.dart`: `isApprover`, `pendingApprovals` from bootstrap.
- New `screens/approvals_screen.dart`: inbox + dynamic transition buttons + note.
- `main_shell.dart`: "Persetujuan" nav/menu entry with badge (gated by `isApprover`).
- Doc detail/list: workflow_state badge for MR. i18n `approval.*`. Rebuild APK.

## Data flow (Purchase MR happy path)

```
Requester (app): create MR(Purchase) → save draft
   └ create_transaction populates stock_ops_approver = leave_approver (throws if none)
Requester (app): "Ajukan" → submit_transaction
   └ workflow-aware → apply "Submit for Approval" → Pending Approval (docstatus 0)
      └ N1 → email + bell to line manager
Line manager (app): Persetujuan inbox → get_workflow_transitions → [Approve, Reject]
   ├ Approve → apply_workflow_action → Approved (docstatus 1 → on_submit)
   │   ├ N2 → email + bell to Purchase Manager
   │   ├ N3 → bell to requester
   │   └ existing web-push notify_doc_submit
   └ Reject (+note) → Rejected (docstatus 0)
       └ N3 → email + bell to requester → Reopen → Draft → revise → resubmit
```

## Error handling / edge cases

- **No approver** → block at submit-for-approval with a clear message (per decision).
- **No hrms / no Employee** (e.g. local `demo.localhost`) → Purchase-MR submit is blocked (expected); the
  workflow install is guarded and Transfer/other flows are unaffected. Approval feature is validated on an
  hrms-enabled bench (halosocia).
- **Non-Purchase MR** → conditional "Submit" transition → straight to Approved/submitted (unchanged UX).
- **Approver lacks Stock Ops role** → `apply_workflow_action` verifies approver identity in code and
  applies the transition server-side, so approvers need not have broad MR permissions.
- **Offline** → creating a draft still queues; the submit-for-approval action requires online (as submit
  does today).
- **Idempotent install** → workflow/notifications matched by fixed names; child rows rebuilt safely.

## Testing plan

1. Backend (hrms bench): Employee + leave_approver set → Purchase MR draft → submit → Pending; approver
   `get_workflow_transitions` returns Approve/Reject; Approve → docstatus 1 + N2 email queued; Reject →
   Rejected → Reopen → Draft. No-approver → blocked. Transfer MR → submits directly.
2. Notifications: assert 3 Notification records exist and fire (Notification Log entries created).
3. App: browser-test the Approvals inbox end-to-end (pending list → approve → disappears; badge updates).
4. Regression: Transfer MR + Stock Entry + Purchase Receipt submit unchanged.

## Deploy

`git pull` on halosocia → **`bench migrate`** (creates Workflow/Notification/custom fields via
after_migrate) → `bench build --app stock_ops` → `bench restart`. Update the wiki + APK afterward.

## Out of scope (future)

Phase 2 AP cycle: Purchase Invoice + Payment Entry (payment terms, taxes & charges). Approval for other
doctypes. Multi-level approval chains.
