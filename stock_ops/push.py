import json

import frappe

DT = "Stock Ops Push Subscription"
VAPID_SUB = "mailto:denzizzy966@gmail.com"


def ensure_vapid_keys():
	"""Buat sepasang kunci VAPID (P-256) sekali, simpan di site_config."""
	if frappe.conf.get("stockops_vapid_private"):
		return
	import base64

	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric import ec
	from frappe.installer import update_site_config

	pk = ec.generate_private_key(ec.SECP256R1())
	priv = pk.private_bytes(
		serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
	).decode()
	pub = pk.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
	pub_b64 = base64.urlsafe_b64encode(pub).rstrip(b"=").decode()
	update_site_config("stockops_vapid_private", priv)
	update_site_config("stockops_vapid_public", pub_b64)


@frappe.whitelist()
def get_public_key():
	ensure_vapid_keys()
	return frappe.conf.get("stockops_vapid_public")


@frappe.whitelist()
def save_subscription(subscription):
	"""Simpan/replace subscription push milik user yang login."""
	if isinstance(subscription, str):
		subscription = json.loads(subscription)
	endpoint = subscription.get("endpoint")
	keys = subscription.get("keys", {})
	if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
		frappe.throw("Subscription tidak valid")

	name = frappe.db.get_value(DT, {"endpoint": endpoint}, "name")
	doc = frappe.get_doc(DT, name) if name else frappe.new_doc(DT)
	doc.update(
		{
			"user": frappe.session.user,
			"endpoint": endpoint,
			"p256dh": keys.get("p256dh"),
			"auth": keys.get("auth"),
			"device": (frappe.get_request_header("User-Agent") or "")[:140],
		}
	)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
def delete_subscription(endpoint):
	name = frappe.db.get_value(DT, {"endpoint": endpoint}, "name")
	if name:
		frappe.delete_doc(DT, name, ignore_permissions=True, force=1)
		frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
def send_test():
	"""Kirim notifikasi uji ke perangkat user saat ini."""
	send_to_user(frappe.session.user, "Stock Ops", "Notifikasi uji berhasil 🎉")
	return {"ok": True}


def _send(sub, payload):
	from pywebpush import WebPushException, webpush

	try:
		webpush(
			subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
			data=json.dumps(payload),
			vapid_private_key=frappe.conf.get("stockops_vapid_private"),
			vapid_claims={"sub": VAPID_SUB},
			timeout=10,
		)
	except WebPushException as e:
		status = getattr(getattr(e, "response", None), "status_code", None)
		if status in (404, 410):  # subscription kedaluwarsa → hapus
			frappe.delete_doc(DT, sub.name, ignore_permissions=True, force=1)
			frappe.db.commit()
		else:
			frappe.log_error(f"web push failed: {e}", "Stock Ops Push")


def _dispatch(filters, title, body, url="/stock_ops/"):
	payload = {"title": title, "body": body, "url": url}
	for s in frappe.get_all(DT, filters=filters, fields=["name", "endpoint", "p256dh", "auth"]):
		_send(frappe._dict(s), payload)


def send_to_user(user, title, body, url="/stock_ops/"):
	_dispatch({"user": user}, title, body, url)


def send_to_all(title, body, url="/stock_ops/"):
	_dispatch({}, title, body, url)


def notify_doc_submit(doc, method=None):
	"""doc_event on_submit untuk Material Request & Stock Entry → push ke semua subscriber."""
	label = {"Material Request": "Permintaan Barang", "Stock Entry": "Stok Barang"}.get(doc.doctype, doc.doctype)
	subtype = getattr(doc, "material_request_type", None) or getattr(doc, "stock_entry_type", "") or ""
	title = f"{doc.name} disubmit"
	body = f"{label} · {subtype} · oleh {frappe.session.user}"
	frappe.enqueue("stock_ops.push.send_to_all", queue="short", title=title, body=body)
