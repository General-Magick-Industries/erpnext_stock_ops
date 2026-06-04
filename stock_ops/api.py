import json

import frappe
from frappe import _

ALLOWED_DOCTYPES = ("Material Request", "Stock Entry")


def get_user_warehouses(user=None):
	"""Gudang milik user.

	Prioritas: gudang yang dipetakan di Employee (field stock_ops_warehouses) →
	lalu User Permission (allow=Warehouse). Kosong = tidak dibatasi (mis. Administrator).
	"""
	user = user or frappe.session.user
	whs = []

	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if emp:
		whs = [
			r.warehouse
			for r in frappe.get_all(
				"Stock Ops Employee Warehouse",
				filters={"parent": emp, "parentfield": "stock_ops_warehouses"},
				fields=["warehouse"],
			)
		]

	if not whs:
		whs = [
			p.for_value
			for p in frappe.get_all(
				"User Permission", filters={"user": user, "allow": "Warehouse"}, fields=["for_value"]
			)
		]

	return list(dict.fromkeys([w for w in whs if w]))


def _resolve_warehouses(warehouse=None, company=None):
	user_whs = get_user_warehouses()
	if warehouse:
		return [warehouse], bool(user_whs)
	if user_whs:
		return user_whs, True
	wfilter = {"disabled": 0, "is_group": 0}
	if company:
		wfilter["company"] = company
	return frappe.get_all("Warehouse", filters=wfilter, pluck="name"), False


@frappe.whitelist()
def resolve_item(code):
	"""Cari item_code dari sebuah kode (item_code, barcode, atau sebagian nama)."""
	code = (code or "").strip()
	if not code:
		return None
	if frappe.db.exists("Item", code):
		return code
	bc = frappe.db.get_value("Item Barcode", {"barcode": code}, "parent")
	if bc:
		return bc
	hit = frappe.get_all("Item", filters={"item_name": ["like", f"%{code}%"]}, pluck="name", limit_page_length=1)
	return hit[0] if hit else None


@frappe.whitelist()
def get_item_detail(item_code, company=None):
	"""Detail item: info, stok per gudang user, & mutasi terakhir."""
	item = frappe.db.get_value(
		"Item", item_code, ["name as item_code", "item_name", "stock_uom", "image", "item_group", "description"], as_dict=True
	)
	if not item:
		frappe.throw(_("Item tidak ditemukan: {0}").format(item_code))

	whs, restricted = _resolve_warehouses(None, company)
	barcodes = frappe.get_all("Item Barcode", filters={"parent": item_code}, pluck="barcode")
	bins = frappe.get_all(
		"Bin",
		filters={"item_code": item_code, "warehouse": ["in", whs or [""]]},
		fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty"],
		order_by="warehouse",
	)
	total = sum(b["actual_qty"] for b in bins)
	moves = frappe.get_all(
		"Stock Ledger Entry",
		filters=[["item_code", "=", item_code], ["warehouse", "in", whs or [""]], ["is_cancelled", "=", 0]],
		fields=["posting_date", "posting_time", "warehouse", "actual_qty", "qty_after_transaction", "voucher_type", "voucher_no"],
		order_by="posting_date desc, posting_time desc, creation desc",
		limit_page_length=20,
	)
	return {
		"item": item,
		"barcodes": barcodes,
		"stock": bins,
		"total": total,
		"uom": item["stock_uom"],
		"movements": moves,
		"warehouses": whs,
		"restricted": restricted,
	}


@frappe.whitelist()
def get_opname_sheet(warehouse, company=None):
	"""Lembar opname: stok sistem saat ini di sebuah gudang (untuk dihitung fisik)."""
	whs, restricted = _resolve_warehouses(None, company)
	if restricted and warehouse not in whs:
		frappe.throw(_("Anda tidak punya akses ke gudang {0}").format(warehouse))

	bins = frappe.get_all(
		"Bin",
		filters={"warehouse": warehouse},
		fields=["item_code", "actual_qty", "valuation_rate", "stock_uom"],
		order_by="item_code",
		limit_page_length=0,
	)
	if bins:
		codes = list({b["item_code"] for b in bins})
		names = {i["name"]: i["item_name"] for i in frappe.get_all("Item", filters={"name": ["in", codes]}, fields=["name", "item_name"])}
		for b in bins:
			b["item_name"] = names.get(b["item_code"], b["item_code"])
	return {"warehouse": warehouse, "items": bins}


@frappe.whitelist()
def create_opname(warehouse, items, company=None, external_localid=None):
	"""Buat Stock Reconciliation (draft) dari hasil hitung fisik. Idempoten via external_localid."""
	if isinstance(items, str):
		items = json.loads(items)
	if not items:
		frappe.throw(_("Tidak ada item untuk direkonsiliasi"))

	if external_localid:
		existing = frappe.db.get_value("Stock Reconciliation", {"external_localid": external_localid}, "name")
		if existing:
			return {"name": existing, "duplicate": True}

	doc = frappe.get_doc(
		{
			"doctype": "Stock Reconciliation",
			"purpose": "Stock Reconciliation",
			"company": company,
			"external_localid": external_localid,
			"items": [
				{
					"item_code": i["item_code"],
					"warehouse": warehouse,
					"qty": i["qty"],
					"valuation_rate": i.get("valuation_rate") or 0,
					"allow_zero_valuation_rate": 1,
				}
				for i in items
			],
		}
	)
	doc.insert()
	frappe.db.commit()
	return {"name": doc.name, "duplicate": False, "count": len(items)}


@frappe.whitelist()
def bulk_purchase_request(items, company=None, external_localid=None):
	"""Buat satu Material Request (Purchase) dari beberapa item terpilih (stok menipis).

	items = [{item_code, qty, uom, warehouse}]. Idempoten via external_localid.
	"""
	if isinstance(items, str):
		items = json.loads(items)
	items = [i for i in items if i.get("item_code") and float(i.get("qty") or 0) > 0]
	if not items:
		frappe.throw(_("Tidak ada item untuk diminta"))

	if external_localid:
		existing = frappe.db.get_value("Material Request", {"external_localid": external_localid}, "name")
		if existing:
			return {"name": existing, "duplicate": True}

	today = frappe.utils.nowdate()
	doc = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": company,
			"transaction_date": today,
			"schedule_date": today,
			"external_localid": external_localid,
			"items": [
				{
					"item_code": i["item_code"],
					"qty": i["qty"],
					"uom": i.get("uom"),
					"schedule_date": today,
					"warehouse": i.get("warehouse"),
				}
				for i in items
			],
		}
	)
	doc.insert()
	frappe.db.commit()
	return {"name": doc.name, "duplicate": False, "count": len(items)}


@frappe.whitelist()
def get_low_stock(company=None, threshold=10):
	"""Item dengan stok menipis di gudang user.

	Batas = reorder level item-per-gudang (Item Reorder) bila ada, jika tidak pakai `threshold`.
	"""
	whs, restricted = _resolve_warehouses(None, company)
	threshold = float(threshold or 0)

	reorders = {}
	for r in frappe.get_all(
		"Item Reorder",
		filters={"warehouse": ["in", whs or [""]]},
		fields=["parent", "warehouse", "warehouse_reorder_level", "warehouse_reorder_qty"],
	):
		reorders[(r.parent, r.warehouse)] = (r.warehouse_reorder_level or 0, r.warehouse_reorder_qty or 0)

	bins = frappe.get_all(
		"Bin",
		filters={"warehouse": ["in", whs or [""]]},
		fields=["item_code", "warehouse", "actual_qty", "projected_qty", "stock_uom"],
		limit_page_length=0,
	)
	low = []
	for b in bins:
		lvl, rqty = reorders.get((b["item_code"], b["warehouse"]), (0, 0))
		limit = lvl if lvl > 0 else threshold
		if limit > 0 and b["actual_qty"] <= limit:
			b["reorder_level"] = lvl
			b["reorder_qty"] = rqty
			b["limit"] = limit
			low.append(b)

	if low:
		codes = list({b["item_code"] for b in low})
		names = {i["name"]: i["item_name"] for i in frappe.get_all("Item", filters={"name": ["in", codes]}, fields=["name", "item_name"])}
		for b in low:
			b["item_name"] = names.get(b["item_code"], b["item_code"])
	low.sort(key=lambda b: (b["actual_qty"] - b["limit"]))
	return {"warehouses": whs, "restricted": restricted, "threshold": threshold, "items": low}


@frappe.whitelist()
def get_stock_ledger(item_code=None, warehouse=None, direction=None, from_date=None, to_date=None, limit=100, company=None):
	"""Pergerakan stok (Stock Ledger Entry) untuk gudang user, dengan filter."""
	whs, restricted = _resolve_warehouses(warehouse, company)
	conds = [["warehouse", "in", whs or [""]], ["is_cancelled", "=", 0]]
	if item_code:
		conds.append(["item_code", "=", item_code])
	if from_date:
		conds.append(["posting_date", ">=", from_date])
	if to_date:
		conds.append(["posting_date", "<=", to_date])
	if direction == "in":
		conds.append(["actual_qty", ">", 0])
	elif direction == "out":
		conds.append(["actual_qty", "<", 0])

	sle = frappe.get_all(
		"Stock Ledger Entry",
		filters=conds,
		fields=[
			"name", "posting_date", "posting_time", "item_code", "warehouse",
			"actual_qty", "qty_after_transaction", "voucher_type", "voucher_no",
		],
		order_by="posting_date desc, posting_time desc, creation desc",
		limit_page_length=int(limit),
	)
	if sle:
		codes = list({s["item_code"] for s in sle})
		meta = {
			i["name"]: i
			for i in frappe.get_all("Item", filters={"name": ["in", codes]}, fields=["name", "item_name", "stock_uom"])
		}
		for s in sle:
			m = meta.get(s["item_code"], {})
			s["item_name"] = m.get("item_name", s["item_code"])
			s["stock_uom"] = m.get("stock_uom", "")
	return {"warehouses": whs, "restricted": restricted, "entries": sle}


@frappe.whitelist()
def get_stock_balance(warehouse=None, company=None):
	"""Saldo stok (dari Bin) untuk gudang user. Dikelompokkan per gudang."""
	whs, restricted = _resolve_warehouses(warehouse, company)

	bins = frappe.get_all(
		"Bin",
		filters={"warehouse": ["in", whs or [""]], "actual_qty": ["!=", 0]},
		fields=["item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty", "stock_uom", "valuation_rate"],
		order_by="warehouse asc, item_code asc",
		limit_page_length=0,
	)
	if bins:
		codes = list({b["item_code"] for b in bins})
		names = {
			i["name"]: i["item_name"]
			for i in frappe.get_all("Item", filters={"name": ["in", codes]}, fields=["name", "item_name"])
		}
		for b in bins:
			b["item_name"] = names.get(b["item_code"], b["item_code"])

	return {"warehouses": whs, "restricted": restricted, "balance": bins}


# Peta key menu (dipakai aplikasi) -> fieldname checkbox di Stock Ops Settings.
MENU_FIELDS = {
	"stock_balance": "show_stock_balance",
	"movement": "show_movement",
	"documents": "show_documents",
	"notifications": "show_notifications",
	"scan": "show_scan",
	"transfer": "show_transfer",
	"low_stock": "show_low_stock",
	"opname": "show_opname",
	"mr": "show_mr",
	"pr": "show_pr",
	"se_in": "show_se_in",
	"se_out": "show_se_out",
	"se_transfer": "show_se_transfer",
}


def _menu_settings():
	"""Flag tampil/sembunyi tiap menu dari Single 'Stock Ops Settings'.
	Default True bila DocType belum ada (belum migrate) atau field belum diset."""
	try:
		s = frappe.get_cached_doc("Stock Ops Settings")
	except Exception:
		s = None
	out = {}
	for key, field in MENU_FIELDS.items():
		val = getattr(s, field, None) if s else None
		out[key] = True if val is None else bool(val)
	return out


@frappe.whitelist()
def get_app_settings():
	"""Hanya flag menu (untuk refresh tanpa bootstrap penuh)."""
	return {"menu": _menu_settings()}


@frappe.whitelist()
def get_bootstrap():
	"""Master data untuk Stock Ops PWA dalam satu panggilan (untuk cache offline)."""
	user = frappe.session.user

	companies = frappe.get_all("Company", fields=["name", "default_currency", "abbr"], order_by="name")
	warehouses = frappe.get_all(
		"Warehouse",
		filters={"disabled": 0},
		fields=["name", "warehouse_name", "company", "is_group"],
		order_by="name",
		limit_page_length=0,
	)
	# hanya warehouse non-group yang bisa dipakai transaksi
	warehouses = [w for w in warehouses if not w.get("is_group")]

	items = frappe.get_all(
		"Item",
		filters={"disabled": 0, "is_stock_item": 1},
		fields=["name as item_code", "item_name", "stock_uom", "image", "item_group"],
		order_by="item_name",
		limit_page_length=0,
	)
	# barcode (opsional) — siapkan map untuk scan nanti
	barcodes = frappe.get_all("Item Barcode", fields=["parent", "barcode"], limit_page_length=0)
	bc_map = {}
	for b in barcodes:
		bc_map.setdefault(b.parent, b.barcode)
	for it in items:
		it["barcode"] = bc_map.get(it["item_code"], "")

	uoms = [u.name for u in frappe.get_all("UOM", filters={"enabled": 1}, fields=["name"], order_by="name", limit_page_length=0)]
	# Supplier bisa tak terbaca oleh role terbatas (mis. Stock User) → jangan gagalkan bootstrap.
	try:
		suppliers = frappe.get_all("Supplier", fields=["name as supplier", "supplier_name"], order_by="supplier_name", limit_page_length=0)
	except frappe.PermissionError:
		suppliers = []

	default_company = frappe.defaults.get_user_default("Company") or (companies[0]["name"] if companies else None)

	return {
		"user": {"name": user, "full_name": frappe.utils.get_fullname(user)},
		"companies": companies,
		"warehouses": warehouses,
		"items": items,
		"uoms": uoms,
		"suppliers": suppliers,
		"defaults": {"company": default_company},
		"user_warehouses": get_user_warehouses(),
		"menu": _menu_settings(),
		"server_time": frappe.utils.now(),
	}


@frappe.whitelist()
def create_transaction(data):
	"""Buat Material Request / Stock Entry sebagai draft, idempoten via external_localid.

	`data` = dict/JSON berisi field dokumen (termasuk `doctype`, `external_localid`, `items`).
	Mengembalikan {name, duplicate}.
	"""
	if isinstance(data, str):
		data = json.loads(data)

	doctype = data.get("doctype")
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype tidak diizinkan: {0}").format(doctype))

	localid = data.get("external_localid")
	if localid:
		existing = frappe.db.get_value(doctype, {"external_localid": localid}, "name")
		if existing:
			return {"name": existing, "duplicate": True}

	doc = frappe.get_doc(data)
	doc.insert()  # tetap draft (docstatus = 0)
	frappe.db.commit()
	return {"name": doc.name, "duplicate": False}


@frappe.whitelist()
def submit_transaction(doctype, name):
	"""Submit dokumen (docstatus 1) — aksi terpisah, online."""
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype tidak diizinkan: {0}").format(doctype))
	doc = frappe.get_doc(doctype, name)
	doc.submit()
	frappe.db.commit()
	return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist()
def cancel_transaction(doctype, name):
	"""Batalkan dokumen submitted (docstatus 2)."""
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype tidak diizinkan: {0}").format(doctype))
	doc = frappe.get_doc(doctype, name)
	doc.cancel()
	frappe.db.commit()
	return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist()
def list_recent(company=None, limit=20):
	"""Dokumen terbaru dari server (MR + Stock Entry) — untuk tab 'Server' di Daftar."""
	limit = int(limit)
	out = []
	mr_filters = {"company": company} if company else {}
	se_filters = {"company": company} if company else {}

	for d in frappe.get_all(
		"Material Request",
		filters=mr_filters,
		fields=["name", "material_request_type as subtype", "transaction_date as date", "status", "docstatus", "modified"],
		order_by="modified desc",
		limit_page_length=limit,
	):
		out.append({"doctype": "Material Request", **d})

	for d in frappe.get_all(
		"Stock Entry",
		filters=se_filters,
		fields=["name", "stock_entry_type as subtype", "posting_date as date", "docstatus", "modified"],
		order_by="modified desc",
		limit_page_length=limit,
	):
		out.append({"doctype": "Stock Entry", "status": None, **d})

	out.sort(key=lambda x: x.get("modified") or "", reverse=True)
	for d in out:
		d.pop("modified", None)
	return out[:limit]


@frappe.whitelist()
def report_counts(company=None):
	"""Ringkasan jumlah dokumen bulan berjalan, per subtipe."""
	from frappe.utils import get_first_day, nowdate

	start = str(get_first_day(nowdate()))
	mr_cond = {"transaction_date": [">=", start]}
	se_cond = {"posting_date": [">=", start]}
	if company:
		mr_cond["company"] = company
		se_cond["company"] = company

	res = {"period": start, "mr": {}, "se": {}}
	for tp in ("Material Transfer", "Purchase"):
		c = frappe.db.count("Material Request", {**mr_cond, "material_request_type": tp})
		if c:
			res["mr"][tp] = c
	for tp in ("Material Receipt", "Material Issue", "Material Transfer"):
		c = frappe.db.count("Stock Entry", {**se_cond, "stock_entry_type": tp})
		if c:
			res["se"][tp] = c
	return res


@frappe.whitelist()
def get_or_create_token():
	"""Setelah login (sesi via /api/method/login), kembalikan api_key + api_secret BARU.

	Dipakai app mobile (Capacitor): login user/password sekali, lalu pakai token auth
	untuk semua request berikutnya (tanpa cookie/CSRF) → ramah lintas-origin.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(frappe._("Harus login"), frappe.AuthenticationError)

	# Set langsung pada user yang sedang login (bukan generate_keys yang butuh System Manager).
	doc = frappe.get_doc("User", user)
	if not doc.api_key:
		doc.api_key = frappe.generate_hash(length=15)
	secret = frappe.generate_hash(length=15)
	doc.api_secret = secret
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"api_key": doc.api_key,
		"api_secret": secret,
		"user": user,
		"full_name": frappe.utils.get_fullname(user),
	}
