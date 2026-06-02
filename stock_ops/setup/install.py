import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

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
	from stock_ops.push import ensure_vapid_keys

	ensure_vapid_keys()


def setup_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	frappe.db.commit()
