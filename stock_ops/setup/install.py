import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

# Custom field untuk idempotensi sync dari Stock Ops PWA.
# Diisi UUID (localId) yang dibuat di klien; dipakai untuk mencegah duplikasi saat retry.
LOCALID_FIELD = {
	"fieldname": "external_localid",
	"label": "External Local ID",
	"fieldtype": "Data",
	"unique": 1,
	"no_copy": 1,
	"hidden": 1,
	"read_only": 1,
	"print_hide": 1,
	"insert_after": "amended_from",
	"description": "Client-generated UUID dari Stock Ops PWA (idempotensi sync offline).",
}

GEO_FIELD = {
	"fieldname": "stock_ops_geolocation",
	"label": "Geolocation (Stock Ops)",
	"fieldtype": "Data",
	"read_only": 1,
	"no_copy": 1,
	"print_hide": 1,
	"insert_after": "external_localid",
	"description": "Koordinat 'lat,lng' saat transaksi dibuat dari Stock Ops PWA.",
}

CUSTOM_FIELDS = {
	"Material Request": [dict(LOCALID_FIELD), dict(GEO_FIELD)],
	"Stock Entry": [dict(LOCALID_FIELD), dict(GEO_FIELD)],
	"Stock Reconciliation": [dict(LOCALID_FIELD)],
	# Pengaitan gudang per employee (dipakai Stock Ops untuk membatasi stok/pergerakan)
	"Employee": [
		{
			"fieldname": "stock_ops_warehouses",
			"label": "Stock Ops Warehouses",
			"fieldtype": "Table MultiSelect",
			"options": "Stock Ops Employee Warehouse",
			"insert_after": "department",
			"description": "Gudang yang dikelola karyawan ini di aplikasi Stock Ops.",
		}
	],
}


def after_install():
	setup_custom_fields()
	setup_roles_and_permissions()
	from stock_ops.push import ensure_vapid_keys

	ensure_vapid_keys()


def after_migrate():
	"""Self-heal saat tiap `bench migrate`: pastikan role & izin aplikasi ada.

	Aman dijalankan berulang (idempoten) — tak menghapus izin yang sudah ada,
	hanya memastikan role Stock Ops dan pemetaan izinnya tetap terpasang.
	"""
	setup_roles_and_permissions()


def setup_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	frappe.db.commit()


# ============================================================
# Role & Permission
# ============================================================
#
# Aplikasi TIDAK punya lapisan izin sendiri: semua aksi tulis (buat/submit/
# cancel) memakai izin standar ERPNext pada doctype-nya. Maka kita siapkan
# dua role khusus saat install, dipetakan ke Material Request / Stock Entry /
# Stock Reconciliation:
#
#   - "Stock Ops User"    : operasional lapangan — buat/ubah/submit dokumen.
#                           TIDAK bisa cancel/hapus. PWA-only (tanpa akses Desk).
#   - "Stock Ops Manager" : semua di atas + cancel/hapus/amend + edit Pengaturan.
#                           Punya akses Desk (lihat Workspace Stock Ops).
#
# Catatan: menambah izin lewat Custom DocPerm membuat ERPNext memakai Custom
# DocPerm sebagai SATU-SATUNYA sumber izin untuk doctype tsb. `add_permission`
# memanggil `setup_custom_perms` lebih dulu (menyalin izin standar utuh), jadi
# izin role bawaan (Stock User/Stock Manager, dll) TETAP terjaga.

ROLE_USER = "Stock Ops User"
ROLE_MANAGER = "Stock Ops Manager"

# Doctype transaksi yang dioperasikan aplikasi (submittable).
TXN_DOCTYPES = ("Material Request", "Stock Entry", "Stock Reconciliation")

# Master data yang cukup dibaca (read-only) oleh aplikasi.
READ_DOCTYPES = (
	"Item",
	"Item Barcode",
	"Item Reorder",
	"Bin",
	"Warehouse",
	"UOM",
	"Company",
	"Supplier",
	"Stock Ledger Entry",
)

_USER_PERMS = {"read": 1, "write": 1, "create": 1, "submit": 1, "print": 1, "email": 1, "report": 1, "export": 1}
_MANAGER_PERMS = {**_USER_PERMS, "cancel": 1, "delete": 1, "amend": 1}


def setup_roles_and_permissions():
	_ensure_role(ROLE_USER, desk_access=0)
	_ensure_role(ROLE_MANAGER, desk_access=1)

	for dt in TXN_DOCTYPES:
		_grant(dt, ROLE_USER, _USER_PERMS)
		_grant(dt, ROLE_MANAGER, _MANAGER_PERMS)

	for dt in READ_DOCTYPES:
		_grant(dt, ROLE_USER, {"read": 1})
		_grant(dt, ROLE_MANAGER, {"read": 1})

	# Pengaturan aplikasi: manajer Stock Ops boleh baca + ubah.
	# (Stock Manager bawaan sudah punya akses lewat doctype JSON.)
	_grant("Stock Ops Settings", ROLE_MANAGER, {"read": 1, "write": 1})

	frappe.db.commit()


def _ensure_role(role_name, desk_access=0):
	if not frappe.db.exists("Role", role_name):
		frappe.get_doc(
			{"doctype": "Role", "role_name": role_name, "desk_access": desk_access}
		).insert(ignore_permissions=True)
	elif frappe.db.get_value("Role", role_name, "desk_access") != desk_access:
		frappe.db.set_value("Role", role_name, "desk_access", desk_access)


def _grant(doctype, role, ptypes):
	"""Pastikan Custom DocPerm (doctype, role, permlevel 0) ada lalu set tiap ptype.

	`add_permission` memanggil `setup_custom_perms` di balik layar (menyalin izin
	standar utuh ke Custom DocPerm) sebelum menambah role baru, jadi izin role
	bawaan tetap terjaga. Kita panggil eksplisit juga sebagai jaring pengaman.
	"""
	if not frappe.db.exists("DocType", doctype):
		return
	try:
		from frappe.permissions import setup_custom_perms

		setup_custom_perms(doctype)
	except Exception:
		pass
	if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
		add_permission(doctype, role, 0)
	for ptype, value in ptypes.items():
		update_permission_property(doctype, role, 0, ptype, value, validate=False)
