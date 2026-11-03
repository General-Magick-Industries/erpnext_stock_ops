// Copyright (c) 2026, RMI and contributors
// For license information, please see license.txt

frappe.ui.form.on("Stock Ops Settings", {
	setup(frm) {
		// Default per User: gudang non-grup milik company baris; user hanya yang aktif.
		const whQuery = (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			const filters = { is_group: 0, disabled: 0 };
			if (row.company) filters.company = row.company;
			return { filters };
		};
		frm.set_query("source_warehouse", "user_defaults", whQuery);
		frm.set_query("target_warehouse", "user_defaults", whQuery);
		frm.set_query("user", "user_defaults", () => ({ filters: { enabled: 1 } }));
	},

	get_users(frm) {
		frappe.call({
			method: "stock_ops.stock_ops.doctype.stock_ops_settings.stock_ops_settings.get_stock_ops_users",
			freeze: true,
			callback(r) {
				const have = new Set((frm.doc.user_defaults || []).map((d) => d.user));
				let added = 0;
				for (const u of r.message || []) {
					if (have.has(u.user)) continue;
					frm.add_child("user_defaults", {
						user: u.user,
						full_name: u.full_name,
						applies_to: "Semua",
						company: u.company,
						source_warehouse: u.source_warehouse,
					});
					added++;
				}
				frm.refresh_field("user_defaults");
				if (added) frm.dirty();
				frappe.show_alert({
					message: added
						? __("{0} user ditambahkan — lengkapi default lalu Simpan.", [added])
						: __("Semua user Stock Ops sudah ada di tabel."),
					indicator: added ? "green" : "blue",
				});
			},
		});
	},
});

frappe.ui.form.on("Stock Ops User Default", {
	user_defaults_add(frm, cdt, cdn) {
		// Baris baru jangan mewarisi default Company milik admin yang sedang mengedit.
		frappe.model.set_value(cdt, cdn, "company", "");
	},

	user(frm, cdt, cdn) {
		// Company mengikuti Employee user bila belum diisi.
		const row = locals[cdt][cdn];
		if (!row.user || row.company) return;
		frappe.db.get_value("Employee", { user_id: row.user }, "company").then((r) => {
			if (r.message && r.message.company) frappe.model.set_value(cdt, cdn, "company", r.message.company);
		});
	},

	company(frm, cdt, cdn) {
		// Ganti company → kosongkan gudang yang bukan milik company baru.
		const row = locals[cdt][cdn];
		for (const f of ["source_warehouse", "target_warehouse"]) {
			if (!row[f] || !row.company) continue;
			frappe.db.get_value("Warehouse", row[f], "company").then((r) => {
				if (r.message && r.message.company !== row.company) frappe.model.set_value(cdt, cdn, f, "");
			});
		}
	},
});
