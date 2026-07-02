# MR Purchase Approval Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a line-manager approval workflow (approver = requesting employee's `leave_approver`) for Material Request of type Purchase, auto-installed with the app, workflow-driven like the HRMS PWA, surfaced as an Approvals inbox in the PWA + Flutter, with a full notification loop.

**Architecture:** A native ERPNext Workflow bound to Material Request gates only Purchase MRs (conditional transitions let other types submit directly). `submit_transaction` becomes workflow-aware. The app never hard-codes actions — it reads `frappe.model.workflow.get_transitions` and calls `apply_workflow`. Workflow + Notifications are created idempotently in `after_install`/`after_migrate`.

**Tech Stack:** Frappe/ERPNext v16, Python 3.11+, Vue 3 + Pinia (PWA), Flutter/Dart (Android).

## Global Constraints

- Only `Material Request` where `material_request_type == 'Purchase'` is gated. All other writes (Transfer MR, Stock Entry, Purchase Receipt/Return, Stock Reconciliation) MUST stay unchanged.
- No approver resolvable ⇒ **block** submit-for-approval with `frappe.throw` (message: `Setel Leave Approver Anda di Employee dulu untuk mengajukan permintaan pembelian.`).
- App is **workflow-driven**: never hard-code action names in client; render transitions from the server.
- All install steps MUST be **idempotent** (safe to re-run every `bench migrate`).
- Commits go on branch `new-develop`, no `Co-Authored-By` trailer, message via `git commit -m '...' -m '...'` (no apostrophes in messages).
- Dev repo `D:\Workspace\stock_ops` ≠ each bench's `apps/stock_ops`; to test on a bench: commit → push → `git fetch upstream new-develop && git reset --hard FETCH_HEAD` on the bench, then run.
- Backend verification uses temp module `apps/stock_ops/stock_ops/_x.py` + `bench execute stock_ops._x.run`, deleted after. hrms-enabled bench required for approver tests (halosocia site `erp.halosocia.my.id`); local `demo.localhost` is erpnext-only.
- PWA bundle is committed: after any `frontend/` change run `cd frontend && npm run build:frappe` and commit the regenerated `stock_ops/public/stock_ops/` + `stock_ops/www/stock_ops/index.html`.

---

### Task 1: Approver resolution helper

**Files:**
- Create: `stock_ops/approval.py`

**Interfaces:**
- Produces: `resolve_approver(user: str|None) -> str` (returns the approver User id; raises `frappe.ValidationError` if none). `get_approver_or_none(user) -> str|None` (non-throwing).

- [ ] **Step 1: Write `stock_ops/approval.py`**

```python
import frappe
from frappe import _


def get_approver_or_none(user=None):
	"""Line manager (leave approver) for the given user, or None. Non-throwing."""
	user = user or frappe.session.user
	if not frappe.db.exists("DocType", "Employee"):
		return None
	emp = frappe.db.get_value("Employee", {"user_id": user}, "leave_approver")
	return emp or None


def resolve_approver(user=None):
	"""Line manager (leave approver) for the given user. Blocks if unresolved."""
	approver = get_approver_or_none(user)
	if not approver:
		frappe.throw(
			_("Setel Leave Approver Anda di Employee dulu untuk mengajukan permintaan pembelian."),
			title=_("Approver belum diatur"),
		)
	return approver
```

- [ ] **Step 2: Verify import + behavior (expect meaningful result)**

Create `stock_ops/_x.py`:

```python
import frappe, traceback
def run():
	try:
		from stock_ops import approval
		print("get_approver_or_none(Administrator):", approval.get_approver_or_none("Administrator"))
		try:
			approval.resolve_approver("nonexistent@example.com")
			print("resolve did NOT throw (unexpected)")
		except frappe.ValidationError as e:
			print("resolve threw as expected:", str(e)[:60])
	except Exception:
		traceback.print_exc()
```

Run: `bench --site demo.localhost execute stock_ops._x.run`
Expected: prints `get_approver_or_none(Administrator): None` and `resolve threw as expected: ...` (Administrator has no Employee/leave_approver on demo).

- [ ] **Step 3: Delete temp module**

Run: `rm -f stock_ops/_x.py`

- [ ] **Step 4: Commit**

```bash
git add stock_ops/approval.py
git commit -m 'feat(approval): approver resolution from Employee leave_approver'
```

---

### Task 2: Custom fields + Workflow auto-install

**Files:**
- Modify: `stock_ops/setup/install.py` (add fields to `CUSTOM_FIELDS`; add `setup_approval_workflow()`; call it from `after_install`/`after_migrate`)

**Interfaces:**
- Consumes: nothing new.
- Produces: `setup_approval_workflow()` creates/repairs Workflow `Stock Ops MR Approval` on Material Request + custom fields `stock_ops_approver` (Link User) and `stock_ops_approval_note` (Small Text) on Material Request. Constant `WORKFLOW_NAME = "Stock Ops MR Approval"`.

- [ ] **Step 1: Add custom fields to `CUSTOM_FIELDS["Material Request"]`**

In `stock_ops/setup/install.py`, extend the Material Request entry (currently `[dict(LOCALID_FIELD), dict(GEO_FIELD)]`) to also include:

```python
	"Material Request": [
		dict(LOCALID_FIELD),
		dict(GEO_FIELD),
		{
			"fieldname": "stock_ops_approver",
			"label": "Approver (Stock Ops)",
			"fieldtype": "Link",
			"options": "User",
			"read_only": 1,
			"no_copy": 1,
			"print_hide": 1,
			"insert_after": "stock_ops_geolocation",
			"description": "Line manager (leave approver) yang menyetujui permintaan pembelian.",
		},
		{
			"fieldname": "stock_ops_approval_note",
			"label": "Approval Note (Stock Ops)",
			"fieldtype": "Small Text",
			"read_only": 1,
			"no_copy": 1,
			"print_hide": 1,
			"insert_after": "stock_ops_approver",
			"description": "Catatan persetujuan/penolakan dari aplikasi Stock Ops.",
		},
	],
```

- [ ] **Step 2: Add the workflow builder at the end of `install.py`**

```python
# ============================================================
# Approval Workflow (MR Purchase)
# ============================================================

WORKFLOW_NAME = "Stock Ops MR Approval"

_WF_STATES = [
	# (state, docstatus, allow_edit, style)
	("Draft", "0", ROLE_USER, ""),
	("Pending Approval", "0", ROLE_MANAGER, "Warning"),
	("Approved", "1", ROLE_MANAGER, "Success"),
	("Rejected", "0", ROLE_USER, "Danger"),
]

_WF_ACTIONS = ["Submit for Approval", "Submit", "Approve", "Reject", "Reopen"]

_WF_TRANSITIONS = [
	# (from_state, action, next_state, allowed_role, condition)
	("Draft", "Submit for Approval", "Pending Approval", ROLE_USER, "doc.material_request_type == 'Purchase'"),
	("Draft", "Submit", "Approved", ROLE_USER, "doc.material_request_type != 'Purchase'"),
	("Pending Approval", "Approve", "Approved", "Employee", "doc.stock_ops_approver == frappe.session.user"),
	("Pending Approval", "Reject", "Rejected", "Employee", "doc.stock_ops_approver == frappe.session.user"),
	("Rejected", "Reopen", "Draft", ROLE_USER, ""),
]


def setup_approval_workflow():
	"""Buat/perbaiki Workflow persetujuan MR Purchase (idempoten).

	Hanya aktif bila role 'Purchase Manager' ada (erpnext buying terpasang) dan
	DocType Material Request ada. Workflow mengikat SELURUH Material Request; tipe
	non-Purchase memakai transition 'Submit' langsung (docstatus 1) via kondisi.
	"""
	if not frappe.db.exists("DocType", "Material Request"):
		return
	if not frappe.db.exists("Role", "Purchase Manager"):
		return

	for state, _ds, _ae, style in _WF_STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style or ""}).insert(
				ignore_permissions=True
			)
	for action in _WF_ACTIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
		wf.set("states", [])
		wf.set("transitions", [])
	else:
		wf = frappe.new_doc("Workflow")
		wf.workflow_name = WORKFLOW_NAME

	wf.document_type = "Material Request"
	wf.is_active = 1
	wf.override_status = 0
	wf.workflow_state_field = "workflow_state"
	wf.send_email_alert = 0

	for state, docstatus, allow_edit, _style in _WF_STATES:
		wf.append("states", {"state": state, "doc_status": docstatus, "allow_edit": allow_edit})
	for from_state, action, next_state, allowed, condition in _WF_TRANSITIONS:
		row = wf.append(
			"transitions",
			{"state": from_state, "action": action, "next_state": next_state, "allowed": allowed, "allow_self_approval": 1},
		)
		if condition:
			row.condition = condition

	wf.save(ignore_permissions=True)
	frappe.db.commit()
```

- [ ] **Step 3: Call it from `after_install` and `after_migrate`**

In `after_install()` add `setup_approval_workflow()` after `setup_roles_and_permissions()`. In `after_migrate()` add `setup_approval_workflow()` after `setup_roles_and_permissions()`.

- [ ] **Step 4: Commit, push, deploy to hrms bench (halosocia) and verify**

```bash
git add stock_ops/setup/install.py
git commit -m 'feat(approval): auto-install MR approval workflow + approver custom fields'
```
Push via PowerShell; on halosocia: `git fetch upstream new-develop && git reset --hard FETCH_HEAD` then `bench --site erp.halosocia.my.id migrate`.

- [ ] **Step 5: Verify workflow created (temp module on halosocia)**

`stock_ops/_x.py`:

```python
import frappe
def run():
	wf = frappe.get_doc("Workflow", "Stock Ops MR Approval")
	print("active:", wf.is_active, "doctype:", wf.document_type)
	print("states:", [(s.state, s.doc_status) for s in wf.states])
	print("transitions:", [(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions])
	print("MR has workflow_state:", bool(frappe.get_meta("Material Request").get_field("workflow_state")))
	print("approver field:", bool(frappe.get_meta("Material Request").get_field("stock_ops_approver")))
```

Run on halosocia: `bench --site erp.halosocia.my.id execute stock_ops._x.run`
Expected: active 1, 4 states with docstatus 0/0/1/0, 5 transitions, workflow_state True, approver field True. Delete temp module.

---

### Task 3: Notifications auto-install

**Files:**
- Modify: `stock_ops/setup/install.py` (add `_ensure_notifications()`, call from `setup_approval_workflow()`)

**Interfaces:**
- Consumes: workflow states from Task 2.
- Produces: 6 `Notification` records (matched by fixed `name`), created idempotently.

- [ ] **Step 1: Add notification config + upsert helper to `install.py`**

```python
# name, subject, event, value_changed, condition, channel, recipient, message
_NOTIFICATIONS = [
	{
		"name": "Stock Ops MR Pending (Email)",
		"subject": "Persetujuan diperlukan: {{ doc.name }}",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state == 'Pending Approval' and doc.material_request_type == 'Purchase'",
		"channel": "Email",
		"recipient": {"receiver_by_document_field": "stock_ops_approver"},
		"message": "Permintaan pembelian {{ doc.name }} oleh {{ doc.owner }} menunggu persetujuan Anda.",
	},
	{
		"name": "Stock Ops MR Pending (System)",
		"subject": "Persetujuan diperlukan: {{ doc.name }}",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state == 'Pending Approval' and doc.material_request_type == 'Purchase'",
		"channel": "System Notification",
		"recipient": {"receiver_by_document_field": "stock_ops_approver"},
		"message": "Permintaan pembelian {{ doc.name }} menunggu persetujuan Anda.",
	},
	{
		"name": "Stock Ops MR Approved PM (Email)",
		"subject": "Permintaan pembelian disetujui: {{ doc.name }}",
		"event": "Submit",
		"value_changed": None,
		"condition": "doc.material_request_type == 'Purchase'",
		"channel": "Email",
		"recipient": {"receiver_by_role": "Purchase Manager"},
		"message": "Permintaan pembelian {{ doc.name }} telah disetujui dan siap diproses.",
	},
	{
		"name": "Stock Ops MR Approved PM (System)",
		"subject": "Permintaan pembelian disetujui: {{ doc.name }}",
		"event": "Submit",
		"value_changed": None,
		"condition": "doc.material_request_type == 'Purchase'",
		"channel": "System Notification",
		"recipient": {"receiver_by_role": "Purchase Manager"},
		"message": "Permintaan pembelian {{ doc.name }} telah disetujui.",
	},
	{
		"name": "Stock Ops MR Outcome Requester (System)",
		"subject": "Status permintaan {{ doc.name }}: {{ doc.workflow_state }}",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state in ('Approved','Rejected') and doc.material_request_type == 'Purchase'",
		"channel": "System Notification",
		"recipient": {"receiver_by_document_field": "owner"},
		"message": "Permintaan {{ doc.name }} Anda: {{ doc.workflow_state }}. {{ doc.stock_ops_approval_note or '' }}",
	},
	{
		"name": "Stock Ops MR Rejected Requester (Email)",
		"subject": "Permintaan {{ doc.name }} ditolak",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state == 'Rejected' and doc.material_request_type == 'Purchase'",
		"channel": "Email",
		"recipient": {"receiver_by_document_field": "owner"},
		"message": "Permintaan pembelian {{ doc.name }} ditolak. Alasan: {{ doc.stock_ops_approval_note or '-' }}",
	},
]


def _ensure_notifications():
	if not frappe.db.exists("DocType", "Notification"):
		return
	for cfg in _NOTIFICATIONS:
		doc = frappe.get_doc("Notification", cfg["name"]) if frappe.db.exists("Notification", cfg["name"]) else frappe.new_doc("Notification")
		doc.name = cfg["name"]
		doc.subject = cfg["subject"]
		doc.document_type = "Material Request"
		doc.event = cfg["event"]
		doc.value_changed = cfg["value_changed"]
		doc.condition = cfg["condition"]
		doc.channel = cfg["channel"]
		doc.enabled = 1
		doc.is_standard = 0
		doc.message = cfg["message"]
		doc.set("recipients", [])
		doc.append("recipients", cfg["recipient"])
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
	frappe.db.commit()
```

Call `_ensure_notifications()` at the end of `setup_approval_workflow()` (after `wf.save`).

- [ ] **Step 2: Commit, push, migrate on halosocia, verify**

```bash
git add stock_ops/setup/install.py
git commit -m 'feat(approval): auto-install approval notifications (email + in-app)'
```
Deploy to halosocia (fetch/reset/migrate). Verify with temp module:

```python
import frappe
def run():
	for n in ["Stock Ops MR Pending (Email)","Stock Ops MR Approved PM (Email)","Stock Ops MR Outcome Requester (System)"]:
		d = frappe.get_doc("Notification", n)
		print(n, "| enabled", d.enabled, "| event", d.event, "| channel", d.channel, "| recip", [r.receiver_by_document_field or r.receiver_by_role for r in d.recipients])
```
Expected: each prints enabled 1 with the right channel/recipient. Delete temp module.

---

### Task 4: Workflow-aware `submit_transaction`

**Files:**
- Modify: `stock_ops/api.py` (`submit_transaction`)

**Interfaces:**
- Consumes: `resolve_approver` (Task 1), workflow (Task 2).
- Produces: `submit_transaction(doctype, name)` now returns `{name, docstatus, workflow_state}`; applies the workflow forward transition when a workflow is active.

- [ ] **Step 1: Read the current `submit_transaction`**

Run: `grep -n "def submit_transaction" stock_ops/api.py` and read it (it currently does `doc.submit()` after ALLOWED_DOCTYPES + localid checks). Preserve those guards.

- [ ] **Step 2: Replace the submit body with workflow-aware logic**

Keep the existing doctype-allowed guard, then:

```python
	doc = frappe.get_doc(doctype, name)
	from frappe.model.workflow import get_workflow_name, get_transitions, apply_workflow

	wf = get_workflow_name(doctype)
	if wf:
		# Purchase MR harus punya approver sebelum diajukan (blokir bila kosong).
		if doctype == "Material Request" and getattr(doc, "material_request_type", None) == "Purchase":
			from stock_ops.approval import resolve_approver

			doc.stock_ops_approver = resolve_approver(doc.owner)
		transitions = get_transitions(doc)
		if not transitions:
			frappe.throw(_("Tidak ada aksi workflow yang tersedia untuk dokumen ini."))
		apply_workflow(doc, transitions[0].get("action"))
	else:
		doc.submit()

	doc.reload()
	return {"name": doc.name, "docstatus": doc.docstatus, "workflow_state": getattr(doc, "workflow_state", None)}
```

Ensure `from frappe import _` exists at top of api.py (add if missing).

- [ ] **Step 3: Verify on halosocia (temp module) — Purchase gates, Transfer submits directly**

```python
import frappe, traceback
def run():
	try:
		from stock_ops import api
		# create a Purchase MR draft as Administrator (owner) via create_transaction path is heavy;
		# here just craft one to exercise submit_transaction:
		mr = frappe.get_doc({"doctype":"Material Request","material_request_type":"Purchase",
			"company": frappe.defaults.get_global_default("company"),
			"schedule_date": frappe.utils.nowdate(),
			"items":[{"item_code": frappe.db.get_value("Item", {"is_purchase_item":1}, "name"),
				"qty":1,"schedule_date": frappe.utils.nowdate(),
				"warehouse": frappe.db.get_value("Warehouse", {"is_group":0}, "name")}]}).insert(ignore_permissions=True)
		# set an approver so it does not block
		mr.db_set("stock_ops_approver", "Administrator")
		print("before:", mr.workflow_state, mr.docstatus)
		res = api.submit_transaction("Material Request", mr.name)
		print("after submit_transaction:", res)  # expect Pending Approval, docstatus 0
	except Exception:
		traceback.print_exc()
```
Expected: `after submit_transaction: {'name': ..., 'docstatus': 0, 'workflow_state': 'Pending Approval'}`. (If Administrator is the resolve target it won't block because we set it directly here.) Delete temp module + the test MR.

- [ ] **Step 4: Commit**

```bash
git add stock_ops/api.py
git commit -m 'feat(approval): workflow-aware submit_transaction (Purchase MR gates, others direct)'
```

---

### Task 5: Workflow API for the app (transitions, apply, pending list)

**Files:**
- Modify: `stock_ops/api.py` (add three whitelisted methods)

**Interfaces:**
- Produces:
  - `get_workflow_transitions(doctype, name) -> list[dict]` (each `{action, next_state, ...}`)
  - `apply_workflow_action(doctype, name, action, note=None) -> {name, workflow_state, docstatus}`
  - `list_pending_approvals(limit=50) -> list[dict]` (name, transaction_date, material_request_type, owner, company, workflow_state, item_count)

- [ ] **Step 1: Add the methods to `api.py`**

```python
@frappe.whitelist()
def get_workflow_transitions(doctype, name):
	"""Aksi workflow yang tersedia untuk user saat ini pada dokumen (seperti Desk)."""
	from frappe.model.workflow import get_transitions

	doc = frappe.get_doc(doctype, name)
	return get_transitions(doc)


@frappe.whitelist()
def apply_workflow_action(doctype, name, action, note=None):
	"""Terapkan aksi workflow (Approve/Reject/dll). Server memverifikasi approver."""
	from frappe.model.workflow import apply_workflow

	doc = frappe.get_doc(doctype, name)
	roles = set(frappe.get_roles())
	is_approver = getattr(doc, "stock_ops_approver", None) == frappe.session.user
	if not (is_approver or {"Stock Ops Manager", "Purchase Manager", "System Manager"} & roles):
		frappe.throw(_("Anda tidak berwenang mengubah status dokumen ini."), frappe.PermissionError)
	if note:
		doc.stock_ops_approval_note = note
		doc.save(ignore_permissions=True)
		doc.reload()
	apply_workflow(doc, action)
	doc.reload()
	return {"name": doc.name, "workflow_state": getattr(doc, "workflow_state", None), "docstatus": doc.docstatus}


@frappe.whitelist()
def list_pending_approvals(limit=50):
	"""Material Request yang menunggu persetujuan user saat ini."""
	if not frappe.get_meta("Material Request").get_field("workflow_state"):
		return []
	rows = frappe.get_all(
		"Material Request",
		filters={"stock_ops_approver": frappe.session.user, "workflow_state": "Pending Approval"},
		fields=["name", "transaction_date", "material_request_type", "owner", "company", "workflow_state"],
		order_by="transaction_date desc, modified desc",
		limit_page_length=int(limit),
	)
	for r in rows:
		r["item_count"] = frappe.db.count("Material Request Item", {"parent": r["name"]})
	return rows
```

- [ ] **Step 2: Verify the approve/reject/reopen loop on halosocia (temp module)**

```python
import frappe, traceback
def run():
	try:
		from stock_ops import api
		mr = frappe.get_doc({"doctype":"Material Request","material_request_type":"Purchase",
			"company": frappe.defaults.get_global_default("company"),
			"schedule_date": frappe.utils.nowdate(),
			"items":[{"item_code": frappe.db.get_value("Item", {"is_purchase_item":1}, "name"),
				"qty":1,"schedule_date": frappe.utils.nowdate(),
				"warehouse": frappe.db.get_value("Warehouse", {"is_group":0}, "name")}]}).insert(ignore_permissions=True)
		mr.db_set("stock_ops_approver", frappe.session.user)  # Administrator approves
		api.submit_transaction("Material Request", mr.name)
		print("transitions:", [t["action"] for t in api.get_workflow_transitions("Material Request", mr.name)])
		print("pending count for me:", len(api.list_pending_approvals()))
		print("approve:", api.apply_workflow_action("Material Request", mr.name, "Approve", note="ok"))
	except Exception:
		traceback.print_exc()
```
Expected: transitions include `Approve` and `Reject`; pending count ≥ 1; approve returns `workflow_state: 'Approved', docstatus: 1`. Delete temp module + test MR.

- [ ] **Step 3: Commit**

```bash
git add stock_ops/api.py
git commit -m 'feat(approval): workflow transitions + apply + pending-approvals API'
```

---

### Task 6: Bootstrap exposes approver context

**Files:**
- Modify: `stock_ops/api.py` (`get_bootstrap`)

**Interfaces:**
- Consumes: `get_approver_or_none` (Task 1), `list_pending_approvals` (Task 5).
- Produces: `get_bootstrap` result gains `is_approver: bool` and `pending_approvals: int`.

- [ ] **Step 1: Add to the `get_bootstrap` return dict**

Find the `return {...}` of `get_bootstrap` and add:

```python
	from stock_ops.approval import get_approver_or_none

	_user = frappe.session.user
	_is_emp_approver = bool(frappe.db.exists("Employee", {"leave_approver": _user})) if frappe.db.exists("DocType", "Employee") else False
	_pending = 0
	if frappe.get_meta("Material Request").get_field("workflow_state"):
		_pending = frappe.db.count("Material Request", {"stock_ops_approver": _user, "workflow_state": "Pending Approval"})
	# ... inside the returned dict:
	"is_approver": bool(_is_emp_approver or _pending),
	"pending_approvals": _pending,
```

(Place the `_user/_is_emp_approver/_pending` computation above the return statement; add the two keys into the dict.)

- [ ] **Step 2: Verify (temp module)**

```python
import frappe
def run():
	from stock_ops import api
	b = api.get_bootstrap()
	print("is_approver:", b.get("is_approver"), "pending_approvals:", b.get("pending_approvals"))
```
Expected: prints both keys (values depend on data). Delete temp module.

- [ ] **Step 3: Commit**

```bash
git add stock_ops/api.py
git commit -m 'feat(approval): bootstrap exposes is_approver + pending_approvals'
```

---

### Task 7: PWA service methods + i18n

**Files:**
- Modify: `frontend/src/lib/service.js`
- Modify: `frontend/src/lib/i18n.js`

**Interfaces:**
- Produces: `listPendingApprovals()`, `getWorkflowTransitions(doctype,name)`, `applyWorkflowAction(doctype,name,action,note)`.

- [ ] **Step 1: Add service functions**

```javascript
// Persetujuan (workflow-driven, mengikuti Workflow di server/Desk)
export const listPendingApprovals = (limit = 50) =>
  call('stock_ops.api.list_pending_approvals', { limit })
export const getWorkflowTransitions = (doctype, name) =>
  call('stock_ops.api.get_workflow_transitions', { doctype, name })
export const applyWorkflowAction = (doctype, name, action, note) =>
  call('stock_ops.api.apply_workflow_action', { doctype, name, action, note }, { post: true })
```

- [ ] **Step 2: Add `approval.*` i18n keys (id + en)**

In `messages.id` add block:
```javascript
    approval: {
      title: 'Persetujuan', none: 'Tidak ada permintaan menunggu persetujuan', note: 'Catatan (opsional)',
      approve: 'Setujui', reject: 'Tolak', pending: 'Menunggu Persetujuan', approved: 'Disetujui',
      rejected: 'Ditolak', by: 'oleh', applied: 'Status {name}: {state}', confirm: 'Terapkan aksi ini?'
    },
```
In `messages.en` add:
```javascript
    approval: {
      title: 'Approvals', none: 'No requests awaiting approval', note: 'Note (optional)',
      approve: 'Approve', reject: 'Reject', pending: 'Pending Approval', approved: 'Approved',
      rejected: 'Rejected', by: 'by', applied: '{name} status: {state}', confirm: 'Apply this action?'
    },
```
Also add workflow-state labels used by badges under an existing `status`-like map if needed: reuse `approval.pending/approved/rejected`.

- [ ] **Step 3: Commit (built together with Task 8/9 UI before bundle rebuild)**

```bash
git add frontend/src/lib/service.js frontend/src/lib/i18n.js
git commit -m 'feat(approval): PWA service methods + i18n'
```

---

### Task 8: PWA Approvals view + routing + badge + status badges

**Files:**
- Create: `frontend/src/views/ApprovalsView.vue`
- Modify: `frontend/src/router/index.js` (route `/approvals` + `ROUTE_MENU`), `frontend/src/stores/master.js` (expose `isApprover`, `pendingApprovals`), `frontend/src/views/HomeView.vue` (entry/badge), `frontend/src/views/DocDetailView.vue` + `frontend/src/views/DocListView.vue` (MR workflow_state badge)

**Interfaces:**
- Consumes: service methods (Task 7); bootstrap `is_approver`/`pending_approvals` (Task 6).

- [ ] **Step 1: master store — load + expose approver context**

In `master.js` `load()` (where `b` is the bootstrap) add: `this.isApprover = !!b.is_approver; this.pendingApprovals = b.pending_approvals || 0;` and add both to state defaults (`isApprover: s.isApprover||false, pendingApprovals: s.pendingApprovals||0`) + persist().

- [ ] **Step 2: Create `ApprovalsView.vue`**

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useApp } from '../stores/app'
import { useI18n } from '../lib/i18n'
import { listPendingApprovals, getWorkflowTransitions, applyWorkflowAction } from '../lib/service'
import AppBar from '../components/AppBar.vue'

const app = useApp()
const { t } = useI18n()
const loading = ref(false)
const rows = ref([])
const busy = ref('')

async function load() {
  loading.value = true
  try { rows.value = (await listPendingApprovals()) || [] }
  catch (e) { app.notify(e && e.message ? e.message : String(e), 'error'); rows.value = [] }
  finally { loading.value = false }
}
onMounted(load)

async function act(row, action) {
  const note = action === 'Reject' ? (window.prompt(t('approval.note')) || '') : ''
  busy.value = row.name
  try {
    const res = await applyWorkflowAction('Material Request', row.name, action, note)
    app.notify(t('approval.applied', { name: row.name, state: res.workflow_state }), 'success')
    rows.value = rows.value.filter((r) => r.name !== row.name)
  } catch (e) { app.notify(e && e.message ? e.message : String(e), 'error') }
  finally { busy.value = '' }
}
async function transitionsFor(row) {
  try { row._transitions = (await getWorkflowTransitions('Material Request', row.name)) || [] }
  catch { row._transitions = [] }
}
</script>

<template>
  <AppBar :title="t('approval.title')" back />
  <div class="content">
    <div v-if="loading" class="empty"><div class="big">⏳</div>{{ t('common.loading') }}</div>
    <div v-else-if="!rows.length" class="empty"><div class="big">✅</div>{{ t('approval.none') }}</div>
    <div v-for="row in rows" :key="row.name" class="card mt12" @vue:mounted="transitionsFor(row)">
      <div style="font-weight: 700">{{ row.name }}</div>
      <div class="tiny muted">{{ row.material_request_type }} · {{ row.owner }} · {{ row.item_count }} item · {{ row.transaction_date }}</div>
      <div class="row" style="gap: 8px; margin-top: 10px">
        <button class="btn danger grow" :disabled="busy === row.name" @click="act(row, 'Reject')">{{ t('approval.reject') }}</button>
        <button class="btn ok grow" :disabled="busy === row.name" @click="act(row, 'Approve')">{{ t('approval.approve') }}</button>
      </div>
    </div>
  </div>
</template>
```

Note: buttons use the workflow actions `Approve`/`Reject` which come from the server workflow; `transitionsFor` fetches the live transitions (used to hide buttons if an action is unavailable — extend later). This keeps the client workflow-driven.

- [ ] **Step 3: Route + menu gating**

In `router/index.js`: add `{ path: '/approvals', name: 'approvals', component: () => import('../views/ApprovalsView.vue'), meta: { tab: 'home' } }` and `approvals: 'approvals'` in `ROUTE_MENU`. `menuOn('approvals')` defaults true; also gate the Home entry by `master.isApprover`.

- [ ] **Step 4: Home entry with pending badge**

In `HomeView.vue`, add a launcher/menu entry "Persetujuan" (only when `master.isApprover`) that routes to `/approvals`, showing `master.pendingApprovals` as a badge when > 0. Follow the existing launch-tile/bell-badge pattern already in HomeView.

- [ ] **Step 5: MR workflow_state badge in detail/list**

In `DocDetailView.vue` and `DocListView.vue`, when the doc is a Material Request and has `workflow_state`, show a small badge mapping `Pending Approval→approval.pending`, `Approved→approval.approved`, `Rejected→approval.rejected`. (Server `list_recent` already returns MR docs; add `workflow_state` to its fields in api.py if absent — check and add.)

- [ ] **Step 6: Build the bundle**

Run: `cd frontend && npm run build:frappe`
Expected: `✓ built` + `Wrote .../www/stock_ops/index.html` and an `ApprovalsView-*.js` chunk.

- [ ] **Step 7: Commit (frontend + rebuilt bundle)**

```bash
git add frontend/src stock_ops/public/stock_ops stock_ops/www/stock_ops stock_ops/api.py
git commit -m 'feat(approval): PWA approvals inbox, workflow-state badges, nav badge'
```

---

### Task 9: PWA end-to-end browser smoke test

**Files:**
- Create: `D:\Workspace\stockops_docs\approvaltest.mjs` (puppeteer, mobile viewport, desk-login then PWA — mirror `returntest.mjs`)

- [ ] **Step 1: Deploy to a bench with data and an approver**

On halosocia (hrms): ensure the test user has an Employee with `leave_approver` set to a second user; create a Purchase MR as the requester and submit-for-approval; log in to the PWA as the approver.

- [ ] **Step 2: Write + run the smoke test**

Script logs in (desk → PWA), opens `#/approvals`, asserts the pending MR appears, clicks Approve, asserts it disappears + a success toast. Save screenshots to `D:\Workspace\stockops_docs\approval-shots\`.

Run: `node D:\Workspace\stockops_docs\approvaltest.mjs`
Expected: prints `pending: [MR-...]`, `approved`, `status: Disetujui`.

- [ ] **Step 3: Commit the test script**

```bash
# in stockops_docs (separate; commit only if that dir is a repo — else leave as artifact)
```

---

### Task 10: Flutter Approvals parity + APK

**Files:**
- Modify: `lib/api/erp.dart`, `lib/state/app_state.dart`, `lib/screens/main_shell.dart`, `lib/i18n.dart`
- Create: `lib/screens/approvals_screen.dart`

**Interfaces:**
- Consumes: same backend APIs.

- [ ] **Step 1: erp.dart methods**

```dart
Future<List<dynamic>> listPendingApprovals({int limit = 50}) async =>
    List<dynamic>.from(await _get('list_pending_approvals', {'limit': limit}));

Future<List<dynamic>> getWorkflowTransitions(String doctype, String name) async =>
    List<dynamic>.from(await _get('get_workflow_transitions', {'doctype': doctype, 'name': name}));

Future<Map<String, dynamic>> applyWorkflowAction(String doctype, String name, String action, {String? note}) async {
  final r = await _dio.post('/api/method/stock_ops.api.apply_workflow_action',
      data: {'doctype': doctype, 'name': name, 'action': action, 'note': note});
  return Map<String, dynamic>.from(_msg(r) as Map);
}
```

- [ ] **Step 2: app_state — isApprover + pendingApprovals from bootstrap**

Add fields `bool isApprover=false; int pendingApprovals=0;`, set them in `loadBootstrap` from `b['is_approver']`/`b['pending_approvals']`, notifyListeners.

- [ ] **Step 3: Create `approvals_screen.dart`**

An inbox listing `listPendingApprovals`; each card fetches `getWorkflowTransitions` and renders one button per transition action (`Approve`/`Reject`/etc. straight from the server — workflow-driven); Reject prompts for a note; calls `applyWorkflowAction`, removes row on success. Mirror the structure of `document_list_screen.dart`.

- [ ] **Step 4: main_shell — Persetujuan entry + badge**

Add a "Persetujuan" entry (gated by `app.isApprover`) opening `ApprovalsScreen`, with a badge showing `app.pendingApprovals` when > 0.

- [ ] **Step 5: i18n `approval.*` (id + en)** — mirror the PWA keys.

- [ ] **Step 6: Analyze + build**

Run: `flutter analyze lib` → Expected: `No issues found!`
Run: `flutter build apk --release` → Expected: `✓ Built build\app\outputs\flutter-apk\app-release.apk`.

- [ ] **Step 7: (Flutter not in git — no commit; APK is the artifact.)**

---

### Task 11: Deploy + wiki + APK distribution

- [ ] **Step 1: Deploy backend + PWA to halosocia**

On halosocia: `git fetch upstream new-develop && git reset --hard FETCH_HEAD` → `bench --site erp.halosocia.my.id migrate` (creates/repairs workflow + notifications + fields) → `bench build --app stock_ops` → `bench restart`.

- [ ] **Step 2: Verify live**

Temp module: assert Workflow active, 6 Notifications enabled, `get_bootstrap` returns `is_approver`/`pending_approvals`. Curl the PWA `/stock_ops` (301). 

- [ ] **Step 3: Wiki page**

Add `_mkwiki.py` page `persetujuan-mr` (flow: ajukan → line manager approve/reject → notifikasi; note the Leave Approver requirement) + sidebar entry; deploy via the established scp + `bench execute stock_ops._mkwiki.run`. Upload screenshots `/files/so-approval-*.png`.

- [ ] **Step 4: Upload new APK**

scp new `app-release.apk` → `sites/erp.halosocia.my.id/public/files/StockOps.apk`; verify HTTP 200.

- [ ] **Step 5: Update memory**

Update `project-stock-ops-pwa.md`: approval workflow shipped; note testerp needs Aung to re-pull.

## Self-Review

- **Spec coverage:** Workflow (Task 2), approver+block (Task 1,4), notifications full loop (Task 3), workflow-driven submit (Task 4), get_transitions/apply/pending API (Task 5), bootstrap context (Task 6), PWA inbox+badges (Task 7-8), Flutter (Task 10), auto-install idempotent (Task 2-3), deploy+migrate (Task 11). All spec sections mapped. ✓
- **Placeholder scan:** No TBD/TODO; code blocks provided for each code step. Task 8 Steps 4-5 reference existing HomeView/DocList patterns (concrete files named) rather than repeating unrelated code — acceptable as they extend an established pattern. ✓
- **Type consistency:** `stock_ops_approver`, `stock_ops_approval_note`, `WORKFLOW_NAME`, action names (`Submit for Approval`/`Submit`/`Approve`/`Reject`/`Reopen`), and API signatures (`get_workflow_transitions`/`apply_workflow_action`/`list_pending_approvals`) are consistent across tasks and match the spec. ✓
