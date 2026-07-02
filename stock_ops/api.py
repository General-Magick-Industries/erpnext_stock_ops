import json

import frappe
from frappe import _

ALLOWED_DOCTYPES = ("Material Request", "Stock Entry", "Purchase Receipt")


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


def get_user_companies(user=None):
	"""Perusahaan yang diizinkan untuk user via **User Permission** (allow=Company).
	Kosong = tidak dibatasi per-perusahaan. Dicek lebih dulu dari default Stock Ops Settings."""
	user = user or frappe.session.user
	return list(
		dict.fromkeys(
			[
				p.for_value
				for p in frappe.get_all(
					"User Permission", filters={"user": user, "allow": "Company"}, fields=["for_value"]
				)
				if p.for_value
			]
		)
	)


def get_user_employee(user=None):
	"""Employee yang tertaut ke user (via Employee.user_id). None bila tidak ada."""
	user = user or frappe.session.user
	return frappe.db.get_value(
		"Employee",
		{"user_id": user},
		["name", "employee_name", "company", "department", "designation"],
		as_dict=True,
	)


@frappe.whitelist()
def get_user_context():
	"""Konteks user untuk aplikasi: Employee, perusahaan, status read-only, dan
	daftar gudang/perusahaan yang boleh diakses. Dipakai untuk mengunci field
	Company dan memfilter picker gudang."""
	scope = _user_scope()
	return {
		"employee": scope["employee"] or None,
		"company": scope["company"],
		"company_read_only": scope["company_read_only"],
		"restricted": scope["restricted"],
		"allowed_warehouses": scope["user_whs"],
		"allowed_companies": scope["allowed_companies"],
		"default_source_warehouse": scope["default_source_warehouse"],
	}


def _warehouse_companies(whs):
	"""Perusahaan (distinct, urut stabil) dari sejumlah gudang."""
	if not whs:
		return []
	rows = frappe.get_all("Warehouse", filters={"name": ["in", whs]}, fields=["company"])
	return list(dict.fromkeys([r.company for r in rows if r.company]))


def _settings_default_company():
	try:
		s = frappe.get_cached_doc("Stock Ops Settings")
		return getattr(s, "default_company", None) or ""
	except Exception:
		return ""


def _user_scope(emp=None):
	"""Lingkup akses user login.

	- `user_whs` = get_user_warehouses() (dari Employee.stock_ops_warehouses ATAU
	  User Permission Warehouse). KOSONG = tidak dibatasi → lihat semua gudang &
	  semua perusahaan (untuk segelintir user/manajer yang dibuka penuh).
	- Bila dibatasi: gudang yang terlihat = `user_whs`; perusahaan = perusahaan
	  gudang tsb; Company dikunci (read-only) bila lingkupnya satu perusahaan.
	"""
	if emp is None:
		emp = get_user_employee()
	# Prioritas: User Permission (Warehouse & Company). Bila kosong → default Stock Ops Settings.
	user_whs = get_user_warehouses()
	up_companies = get_user_companies()
	restricted = bool(user_whs) or bool(up_companies)

	# Perusahaan yang diizinkan: User Permission Company diutamakan; jika tidak ada tapi
	# gudang dibatasi, pakai perusahaan gudang tsb; selain itu tak dibatasi.
	if up_companies:
		allowed_companies = up_companies
	elif user_whs:
		allowed_companies = _warehouse_companies(user_whs)
	else:
		allowed_companies = []

	# Perusahaan default: Employee (bila dalam lingkup) → lingkup pertama → Settings → pertama.
	if emp and emp.get("company") and (not allowed_companies or emp["company"] in allowed_companies):
		company = emp["company"]
	elif allowed_companies:
		company = allowed_companies[0]
	else:
		company = _settings_default_company() or frappe.defaults.get_user_default("Company")
		if not company:
			first = frappe.get_all("Company", pluck="name", limit_page_length=1)
			company = first[0] if first else None

	if restricted and allowed_companies and company not in allowed_companies:
		company = allowed_companies[0]

	# Kunci Company hanya bila lingkup tepat satu perusahaan.
	company_read_only = bool(restricted and len(allowed_companies) == 1 and company)

	# Gudang sumber default — pakai Settings; bila gudang dibatasi & tak valid, gudang pertama user.
	src = _default_source_warehouse()
	if user_whs and (not src or src not in user_whs):
		src = user_whs[0]

	return {
		"employee": emp,
		"user_whs": user_whs,
		"up_companies": up_companies,
		"restricted": restricted,
		"allowed_companies": allowed_companies,
		"company": company,
		"company_read_only": company_read_only,
		"default_source_warehouse": src,
	}


def _collect_warehouses(data):
	"""Kumpulkan semua nilai gudang dari sebuah payload dokumen (top-level + item)."""
	keys = ("from_warehouse", "to_warehouse", "s_warehouse", "t_warehouse", "set_warehouse", "warehouse")
	whs = set()
	for k in keys:
		v = data.get(k)
		if v:
			whs.add(v)
	for it in (data.get("items") or []):
		for k in ("warehouse", "s_warehouse", "t_warehouse"):
			v = it.get(k)
			if v:
				whs.add(v)
	return whs


def _assert_warehouses_allowed(whs):
	"""Tolak bila ada gudang di luar lingkup user (saat user dibatasi). Aman bila tak dibatasi.
	Lingkup gudang (User Permission Warehouse / Employee) diutamakan; bila tak ada tapi user
	dibatasi per-perusahaan (User Permission Company), tolak gudang di luar perusahaan itu."""
	allowed = get_user_warehouses()
	if allowed:
		bad = sorted(w for w in whs if w and w not in allowed)
		if bad:
			frappe.throw(_("Anda tidak punya akses ke gudang: {0}").format(", ".join(bad)))
		return
	up_companies = get_user_companies()
	if up_companies:
		wanted = [w for w in whs if w]
		co = {r.name: r.company for r in frappe.get_all("Warehouse", filters={"name": ["in", wanted]}, fields=["name", "company"])} if wanted else {}
		bad = sorted(w for w in wanted if co.get(w) not in up_companies)
		if bad:
			frappe.throw(_("Anda tidak punya akses ke gudang: {0}").format(", ".join(bad)))


def _default_source_warehouse():
	try:
		s = frappe.get_cached_doc("Stock Ops Settings")
		return getattr(s, "default_source_warehouse", None) or ""
	except Exception:
		return ""


def _resolve_warehouses(warehouse=None, company=None):
	user_whs = get_user_warehouses()
	up_companies = get_user_companies()
	if warehouse:
		return [warehouse], bool(user_whs) or bool(up_companies)
	if user_whs:
		return user_whs, True
	wfilter = {"disabled": 0, "is_group": 0}
	if company:
		wfilter["company"] = company
	elif up_companies:
		wfilter["company"] = ["in", up_companies]
	return frappe.get_all("Warehouse", filters=wfilter, pluck="name"), bool(up_companies)


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
def list_open_purchase_orders(company=None, supplier=None, search=None, limit=50):
	"""Purchase Order yang masih bisa diterima (belum 100% diterima) — untuk Penerimaan Barang."""
	filters = {
		"docstatus": 1,
		"status": ["not in", ["Closed", "Completed", "Cancelled", "On Hold"]],
		"per_received": ["<", 100],
	}
	if company:
		filters["company"] = company
	if supplier:
		filters["supplier"] = supplier
	if search:
		filters["name"] = ["like", "%" + search + "%"]
	return frappe.get_all(
		"Purchase Order",
		filters=filters,
		fields=["name", "supplier", "supplier_name", "transaction_date", "status", "company", "per_received", "grand_total", "currency"],
		order_by="transaction_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_purchase_order_items(purchase_order):
	"""Item PO yang belum diterima penuh → untuk auto-isi form Penerimaan Barang.

	Tiap baris membawa purchase_order + purchase_order_item (po_detail) agar Purchase
	Receipt ter-link ke PO; ERPNext memvalidasi qty terima terhadap qty pesan.
	"""
	po = frappe.get_doc("Purchase Order", purchase_order)
	out = []
	for it in po.items:
		remaining = (it.qty or 0) - (it.received_qty or 0)
		if remaining <= 0:
			continue
		out.append({
			"item_code": it.item_code,
			"item_name": it.item_name,
			"uom": it.uom or it.stock_uom,
			"qty": remaining,
			"rate": it.rate,
			"warehouse": it.warehouse,
			"is_fixed_asset": int(frappe.db.get_value("Item", it.item_code, "is_fixed_asset") or 0),
			"purchase_order": po.name,
			"purchase_order_item": it.name,
		})
	return {
		"name": po.name,
		"supplier": po.supplier,
		"supplier_name": po.supplier_name,
		"company": po.company,
		"set_warehouse": po.get("set_warehouse"),
		"items": out,
	}


@frappe.whitelist()
def list_returnable_receipts(company=None, supplier=None, search=None, limit=50):
	"""Purchase Receipt yang sudah disubmit & bisa diretur (bukan dokumen retur)."""
	filters = {"docstatus": 1, "is_return": 0}
	if company:
		filters["company"] = company
	if supplier:
		filters["supplier"] = supplier
	if search:
		filters["name"] = ["like", "%" + search + "%"]
	return frappe.get_all(
		"Purchase Receipt",
		filters=filters,
		fields=["name", "supplier", "supplier_name", "posting_date", "company", "per_returned", "grand_total", "currency"],
		order_by="posting_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_receipt_items_for_return(purchase_receipt):
	"""Item Purchase Receipt untuk diretur beserta **sisa qty yang masih bisa diretur**.

	Sisa dihitung lewat `make_return_doc` (mengurangi qty yang sudah diretur pada
	dokumen retur sebelumnya) — lebih andal daripada field `per_returned` yang bisa basi.
	"""
	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	pr = frappe.get_doc("Purchase Receipt", purchase_receipt)
	remaining = {}
	try:
		ret = make_return_doc("Purchase Receipt", purchase_receipt)
		for it in ret.items:
			# make_return_doc memberi qty negatif = sisa yang masih bisa diretur
			remaining[it.purchase_receipt_item] = abs(it.qty or 0)
	except Exception:
		remaining = {}

	out = []
	for it in pr.items:
		max_qty = remaining.get(it.name, it.qty) if remaining else it.qty
		out.append({
			"item_code": it.item_code,
			"item_name": it.item_name,
			"uom": it.uom,
			"qty": it.qty,  # qty diterima asli
			"returnable_qty": max_qty,  # sisa yang masih bisa diretur
			"warehouse": it.warehouse,
			"purchase_receipt_item": it.name,
		})
	return {"name": pr.name, "supplier": pr.supplier, "supplier_name": pr.supplier_name, "company": pr.company, "items": out}


@frappe.whitelist()
def create_purchase_return(purchase_receipt, items=None, external_localid=None):
	"""Buat dokumen **retur barang** (Purchase Receipt is_return=1) atas sebuah Purchase
	Receipt: qty negatif & return_against terisi (stok berkurang saat di-submit).

	`items` opsional = [{item_code, qty}] untuk retur sebagian; kosong = retur penuh.
	Idempoten via external_localid. Mengembalikan draft (submit lewat submit_transaction).
	"""
	if isinstance(items, str):
		items = json.loads(items)
	if external_localid:
		existing = frappe.db.get_value("Purchase Receipt", {"external_localid": external_localid}, "name")
		if existing:
			return {"name": existing, "duplicate": True}

	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	ret = make_return_doc("Purchase Receipt", purchase_receipt)

	# Retur sebagian: sesuaikan qty per item (negatif) & buang item yang tak diretur.
	if items:
		want = {}
		for i in items:
			code = i.get("item_code")
			qty = abs(float(i.get("qty") or 0))
			if code and qty:
				want[code] = qty
		kept = []
		for it in ret.items:
			if it.item_code in want:
				it.qty = -want[it.item_code]
				it.received_qty = it.qty
				it.rejected_qty = 0
				kept.append(it)
		if kept:
			ret.set("items", kept)

	if external_localid:
		ret.external_localid = external_localid
	ret.insert()
	frappe.db.commit()
	return {"name": ret.name, "duplicate": False}


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

	_assert_warehouses_allowed({warehouse})

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

	_assert_warehouses_allowed({i.get("warehouse") for i in items if i.get("warehouse")})

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
	"grn": "show_purchase_receipt",
}


def _menu_settings(settings=None):
	"""Flag tampil/sembunyi tiap menu, dengan override per-role.

	- Default per menu = field global `show_*` (True bila belum migrate/diset).
	- Bila sebuah menu punya baris override untuk salah satu role user, nilai
	  role dipakai (OR antar role: tampil bila ada role yang mengizinkan).
	"""
	s = settings
	if s is None:
		try:
			s = frappe.get_cached_doc("Stock Ops Settings")
		except Exception:
			s = None

	# Pakai nilai yang BENAR-BENAR tersimpan (tabSingles). Field yang belum pernah
	# diset (mis. menu baru ditambah lewat migrate ke doc lama) TIDAK muncul di sini,
	# sehingga default-nya "tampil" (True) — bukan 0/hidden akibat Check di-load jadi 0.
	try:
		stored = frappe.db.get_singles_dict("Stock Ops Settings") or {}
	except Exception:
		stored = {}

	base = {}
	for key, field in MENU_FIELDS.items():
		if field in stored:
			base[key] = bool(int(stored[field] or 0))
		else:
			base[key] = True  # belum diset → tampil secara default

	# Kumpulkan override yang berlaku untuk role user
	roles = set(frappe.get_roles(frappe.session.user))
	applicable = {}  # menu -> list[bool]
	for row in (getattr(s, "menu_overrides", None) or []):
		if row.role in roles and row.menu in MENU_FIELDS:
			applicable.setdefault(row.menu, []).append(bool(row.visible))

	out = {}
	for key in MENU_FIELDS:
		out[key] = any(applicable[key]) if key in applicable else base[key]
	return out


def _user_caps():
	"""Kemampuan user (untuk UI sembunyikan aksi yang tak diizinkan).

	Penegakan tetap di server (API patuh izin standar); ini hanya supaya tombol
	cancel/hapus tak ditampilkan ke Stock Ops User biasa.
	"""
	roles = set(frappe.get_roles(frappe.session.user))
	is_manager = frappe.session.user == "Administrator" or any(
		r in roles for r in ("System Manager", "Stock Manager", "Stock Ops Manager")
	)
	can_cancel = is_manager or any(
		frappe.has_permission(dt, ptype="cancel") for dt in ("Material Request", "Stock Entry")
	)
	return {"is_manager": is_manager, "can_cancel": bool(can_cancel)}


def _app_settings():
	try:
		s = frappe.get_cached_doc("Stock Ops Settings")
	except Exception:
		s = None
	default_lang = (getattr(s, "default_language", None) or "id") if s else "id"
	apk_url = (getattr(s, "flutter_apk_url", None) or "") if s else ""
	return {
		"menu": _menu_settings(s),
		"default_lang": default_lang,
		"flutter_apk_url": apk_url,
		"default_source_warehouse": (getattr(s, "default_source_warehouse", None) or "") if s else "",
		"caps": _user_caps(),
	}


@frappe.whitelist()
def get_app_settings():
	"""Menu flags + bahasa default (untuk refresh tanpa bootstrap penuh)."""
	return _app_settings()


@frappe.whitelist()
def get_notifications(limit=20):
	"""Notifikasi in-app (Notification Log) untuk user login — dipoll aplikasi (tanpa Firebase)."""
	user = frappe.session.user
	items = frappe.get_all(
		"Notification Log",
		filters={"for_user": user},
		fields=["name", "subject", "type", "document_type", "document_name", "read", "creation", "from_user"],
		order_by="creation desc",
		limit_page_length=int(limit),
	)
	unread = frappe.db.count("Notification Log", {"for_user": user, "read": 0})
	return {"items": items, "unread": unread}


@frappe.whitelist()
def mark_notifications_read(name=None):
	"""Tandai satu (name) atau semua notifikasi user sebagai sudah dibaca."""
	user = frappe.session.user
	if name:
		if frappe.db.get_value("Notification Log", name, "for_user") == user:
			frappe.db.set_value("Notification Log", name, "read", 1)
	else:
		frappe.db.sql("UPDATE `tabNotification Log` SET `read`=1 WHERE for_user=%s AND `read`=0", user)
	frappe.db.commit()
	return {"ok": True}


def has_app_permission():
	"""Siapa yang melihat tile Stock Ops di App Switcher desk.
	Dibatasi ke manajer; Stock Ops User biasa cukup pakai PWA (/stock_ops)."""
	if frappe.session.user == "Administrator":
		return True
	roles = set(frappe.get_roles())
	return any(r in roles for r in ("System Manager", "Stock Manager", "Stock Ops Manager"))


@frappe.whitelist()
def get_bootstrap():
	"""Master data untuk Stock Ops PWA dalam satu panggilan (untuk cache offline)."""
	user = frappe.session.user

	scope = _user_scope()

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

	# Batasi daftar gudang & perusahaan sesuai lingkup user (Employee.stock_ops_warehouses
	# / User Permission). User tanpa batasan tetap melihat semua.
	if scope["restricted"]:
		if scope["allowed_companies"]:
			allowed_co = set(scope["allowed_companies"])
			companies = [c for c in companies if c["name"] in allowed_co]
		if scope["user_whs"]:
			# dibatasi per-gudang (User Permission Warehouse / Employee)
			allowed_wh = set(scope["user_whs"])
			warehouses = [w for w in warehouses if w["name"] in allowed_wh]
		elif scope["allowed_companies"]:
			# dibatasi per-perusahaan saja → tampilkan gudang perusahaan tsb
			allowed_co = set(scope["allowed_companies"])
			warehouses = [w for w in warehouses if w.get("company") in allowed_co]

	items = frappe.get_all(
		"Item",
		filters={"disabled": 0},
		or_filters=[{"is_stock_item": 1}, {"is_fixed_asset": 1}],
		fields=["name as item_code", "item_name", "stock_uom", "image", "item_group", "is_fixed_asset"],
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

	# Lokasi aset (untuk penerimaan barang yang berupa fixed asset). Modul/akses bisa tak ada.
	try:
		locations = frappe.get_all("Location", filters={"is_group": 0}, pluck="name", order_by="name", limit_page_length=0)
	except Exception:
		locations = []

	company = scope["company"] or (companies[0]["name"] if companies else None)
	_app = _app_settings()

	# Konteks persetujuan: apakah user seorang approver (leave approver) + jumlah antrean.
	is_emp_approver = (
		bool(frappe.db.exists("Employee", {"leave_approver": user})) if frappe.db.exists("DocType", "Employee") else False
	)
	pending_approvals = 0
	if frappe.get_meta("Material Request").get_field("workflow_state"):
		pending_approvals = frappe.db.count(
			"Material Request", {"stock_ops_approver": user, "workflow_state": "Pending Approval"}
		)

	return {
		"user": {"name": user, "full_name": frappe.utils.get_fullname(user)},
		"employee": scope["employee"] or None,
		"companies": companies,
		"warehouses": warehouses,
		"items": items,
		"uoms": uoms,
		"suppliers": suppliers,
		"locations": locations,
		"defaults": {
			"company": company,
			"company_read_only": scope["company_read_only"],
			"source_warehouse": scope["default_source_warehouse"],
		},
		"restricted": scope["restricted"],
		"user_warehouses": scope["user_whs"],
		"menu": _app["menu"],
		"default_lang": _app["default_lang"],
		"flutter_apk_url": _app["flutter_apk_url"],
		"caps": _app["caps"],
		"is_approver": bool(is_emp_approver or pending_approvals),
		"pending_approvals": pending_approvals,
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

	_assert_warehouses_allowed(_collect_warehouses(data))

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
	"""Finalkan dokumen — aksi terpisah, online.

	Bila doctype punya Workflow aktif (mis. Material Request), TIDAK memanggil
	doc.submit() langsung; melainkan menerapkan transition maju sesuai Workflow
	(seperti Desk). Untuk MR Purchase → 'Submit for Approval' (tetap draft, menunggu
	persetujuan); tipe lain → 'Submit' (docstatus 1). Doctype tanpa workflow → submit biasa.
	"""
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype tidak diizinkan: {0}").format(doctype))
	doc = frappe.get_doc(doctype, name)

	from frappe.model.workflow import apply_workflow, get_transitions, get_workflow_name

	if get_workflow_name(doctype):
		# MR Purchase wajib punya approver (leave approver) sebelum diajukan — blokir bila kosong.
		if doctype == "Material Request" and getattr(doc, "material_request_type", None) == "Purchase":
			from stock_ops.approval import resolve_approver

			doc.stock_ops_approver = resolve_approver(doc.owner)
		transitions = get_transitions(doc)
		if not transitions:
			frappe.throw(_("Tidak ada aksi workflow yang tersedia untuk dokumen ini."))
		apply_workflow(doc, transitions[0].get("action"))
	else:
		doc.submit()

	frappe.db.commit()
	doc.reload()
	return {"name": doc.name, "docstatus": doc.docstatus, "workflow_state": getattr(doc, "workflow_state", None)}


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
	frappe.db.commit()
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


@frappe.whitelist()
def list_recent(company=None, limit=20):
	"""Dokumen terbaru dari server (MR + Stock Entry) — untuk tab 'Server' di Daftar."""
	limit = int(limit)
	out = []
	mr_filters = {"company": company} if company else {}
	se_filters = {"company": company} if company else {}

	mr_fields = ["name", "material_request_type as subtype", "transaction_date as date", "status", "docstatus", "modified"]
	if frappe.get_meta("Material Request").get_field("workflow_state"):
		mr_fields.append("workflow_state")
	for d in frappe.get_all(
		"Material Request",
		filters=mr_filters,
		fields=mr_fields,
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

	for d in frappe.get_all(
		"Purchase Receipt",
		filters=({"company": company} if company else {}),
		fields=["name", "supplier as subtype", "posting_date as date", "status", "docstatus", "modified"],
		order_by="modified desc",
		limit_page_length=limit,
	):
		out.append({"doctype": "Purchase Receipt", **d})

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
