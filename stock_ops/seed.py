"""Seeder data uji untuk Stock Ops (khusus test/dev — JANGAN dipakai di produksi).

Pemakaian di bench:
    bench --site <site> execute stock_ops.seed.run
    bench --site <site> execute stock_ops.seed.run --kwargs "{'count':100,'with_requests':True}"
    bench --site <site> execute stock_ops.seed.wipe        # hapus semua data demo (prefix DEMO-)

Otomatis memilih company default & gudang non-group pertama bila tidak diberikan.
Idempoten: item dengan prefix dilewati bila sudah ada; stok diterima sekali.
"""

import random

import frappe

PREFIX = "DEMO-"


def _pick_company(company=None):
	if company:
		return company
	c = frappe.defaults.get_global_default("company")
	if c:
		return c
	rows = frappe.get_all("Company", pluck="name", limit_page_length=1)
	if not rows:
		frappe.throw("Tidak ada Company di site ini.")
	return rows[0]


def _pick_warehouses(company, warehouse=None):
	if warehouse:
		return [warehouse]
	whs = frappe.get_all(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		pluck="name",
		order_by="creation",
		limit_page_length=3,
	)
	if not whs:
		frappe.throw(f"Tidak ada Warehouse (non-group) untuk company {company}.")
	return whs


def _item_group():
	g = frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name", limit_page_length=1)
	return g[0] if g else "All Item Groups"


def _uom():
	return "Nos" if frappe.db.exists("UOM", "Nos") else (frappe.get_all("UOM", pluck="name", limit_page_length=1) or ["Nos"])[0]


def run(count=50, company=None, warehouse=None, with_requests=True, seed=7):
	"""Buat `count` item demo + stok (sebagian di bawah reorder level) + opsional MR draft."""
	count = int(count)
	random.seed(int(seed))
	company = _pick_company(company)
	whs = _pick_warehouses(company, warehouse)
	wh_main = whs[0]
	wh_2 = whs[1] if len(whs) > 1 else whs[0]
	grp = _item_group()
	uom = _uom()

	# 1) Items + reorder level
	created = 0
	for i in range(1, count + 1):
		code = f"{PREFIX}{i:04d}"
		if frappe.db.exists("Item", code):
			continue
		d = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": f"Demo Item {i:03d}",
				"item_group": grp,
				"stock_uom": uom,
				"is_stock_item": 1,
				"is_purchase_item": 1,
			}
		)
		d.append("barcodes", {"barcode": f"{PREFIX}BC{i:06d}"})
		d.append(
			"reorder_levels",
			{"warehouse": wh_main, "warehouse_reorder_level": 20, "warehouse_reorder_qty": 100, "material_request_type": "Purchase"},
		)
		d.insert(ignore_permissions=True)
		created += 1
	frappe.db.commit()

	# 2) Stok via Material Receipt (sebagian rendah). Guard: lewati bila item terakhir sudah punya stok.
	last = f"{PREFIX}{count:04d}"
	has_stock = frappe.db.get_value("Bin", {"item_code": last, "warehouse": wh_main, "actual_qty": [">", 0]}, "name")
	received = 0
	if not has_stock:
		low_n = max(1, count // 3)

		def rows(a, b, lo, hi):
			return [(f"{PREFIX}{i:04d}", random.randint(lo, hi)) for i in range(a, b + 1)]

		def receipt(wh, items):
			se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "company": company})
			for code, qty in items:
				se.append(
					"items",
					{"item_code": code, "qty": qty, "t_warehouse": wh, "basic_rate": random.randint(1000, 50000), "allow_zero_valuation_rate": 1},
				)
			se.insert(ignore_permissions=True)
			se.submit()
			return len(items)

		# item 1..low_n => rendah (3..18); sisanya normal (30..300). Chunk 40 agar dokumen tak terlalu besar.
		allrows = rows(1, low_n, 3, 18) + rows(low_n + 1, count, 30, 300)
		for j in range(0, len(allrows), 40):
			received += receipt(wh_main, allrows[j : j + 40])
		if wh_2 != wh_main:
			receipt(wh_2, rows(1, min(count, 40), 20, 150))
		frappe.db.commit()

	# 3) Material Request draft (opsional)
	mr_made = 0
	if with_requests:
		for i in range(1, 21):
			lid = f"demo-mr-{i:03d}"
			if frappe.db.exists("Material Request", {"external_localid": lid}):
				continue
			typ = "Purchase" if i % 3 else "Material Transfer"
			items = []
			for _ in range(random.randint(1, 4)):
				items.append(
					{
						"item_code": f"{PREFIX}{random.randint(1, count):04d}",
						"qty": random.randint(5, 50),
						"uom": uom,
						"schedule_date": frappe.utils.nowdate(),
						"warehouse": wh_main,
						**({"from_warehouse": wh_2} if typ == "Material Transfer" else {}),
					}
				)
			mr = frappe.get_doc(
				{
					"doctype": "Material Request",
					"material_request_type": typ,
					"company": company,
					"transaction_date": frappe.utils.nowdate(),
					"schedule_date": frappe.utils.nowdate(),
					"external_localid": lid,
					"items": items,
				}
			)
			mr.insert(ignore_permissions=True)
			mr_made += 1
		frappe.db.commit()

	result = {
		"company": company,
		"warehouse_main": wh_main,
		"items_created": created,
		"receipts_lines": received,
		"mr_drafts": mr_made,
		"total_demo_items": frappe.db.count("Item", {"item_code": ["like", f"{PREFIX}%"]}),
	}
	print(result)
	return result


def wipe():
	"""Hapus semua data demo (item, stok terkait, MR demo). Untuk membersihkan test server."""
	# Material Request demo
	for n in frappe.get_all("Material Request", filters={"external_localid": ["like", "demo-mr-%"]}, pluck="name"):
		d = frappe.get_doc("Material Request", n)
		if d.docstatus == 1:
			d.cancel()
		frappe.delete_doc("Material Request", n, force=1, ignore_permissions=True)

	codes = frappe.get_all("Item", filters={"item_code": ["like", f"{PREFIX}%"]}, pluck="name")
	# Batalkan Stock Entry yang memuat item demo, lalu hapus
	se_names = set()
	for code in codes:
		for r in frappe.get_all("Stock Entry Detail", filters={"item_code": code}, fields=["parent"]):
			se_names.add(r.parent)
	for n in se_names:
		try:
			d = frappe.get_doc("Stock Entry", n)
			if d.docstatus == 1:
				d.cancel()
			frappe.delete_doc("Stock Entry", n, force=1, ignore_permissions=True)
		except Exception as e:
			print("skip SE", n, e)
	for code in codes:
		try:
			frappe.delete_doc("Item", code, force=1, ignore_permissions=True)
		except Exception as e:
			print("skip Item", code, e)
	frappe.db.commit()
	print({"deleted_items": len(codes), "cancelled_stock_entries": len(se_names)})
	return {"deleted_items": len(codes), "cancelled_stock_entries": len(se_names)}
