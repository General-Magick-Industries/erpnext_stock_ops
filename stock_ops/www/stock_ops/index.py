import frappe

no_cache = 1


def get_context(context):
	# Wajib login — tamu diarahkan ke halaman login Frappe.
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/stock_ops"
		raise frappe.Redirect

	context.csrf_token = frappe.sessions.get_csrf_token()
	context.stockops_user = frappe.session.user
	frappe.db.commit()  # nosemgrep
	return context
