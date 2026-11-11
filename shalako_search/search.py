import re

import frappe
from frappe.utils import cstr

MAX_RESULTS = 8
# Built-in "Search for ..." sits at index 100; everything here ranks above it.
RANK_EXACT, RANK_STARTS, RANK_WORD_STARTS, RANK_CONTAINS, RANK_ID = 200, 190, 180, 170, 195


def _rank(name: str, txt: str) -> int:
	n, t = name.lower().strip(), txt.lower().strip()
	if n == t:
		return RANK_EXACT
	if n.startswith(t):
		return RANK_STARTS
	words = re.split(r"[\s/&,.\-()]+", n)
	if any(w.startswith(t) for w in words if w):
		return RANK_WORD_STARTS
	return RANK_CONTAINS


def customer_results(txt: str) -> list[dict]:
	txt = cstr(txt).strip()
	if len(txt) < 2 or not frappe.has_permission("Customer", "read"):
		return []

	fields = ["name", "customer_name", "disabled"]
	meta = frappe.get_meta("Customer")
	for f in ("custom_netsuite_id", "custom_ops_status", "custom_county", "custom_open_cases"):
		if meta.has_field(f):
			fields.append(f)

	found = {}

	# Name match: every word typed must appear somewhere in the customer name.
	tokens = [t for t in re.split(r"\s+", txt) if t][:5]
	name_filters = [["customer_name", "like", f"%{t}%"] for t in tokens]
	for row in frappe.get_list("Customer", fields=fields, filters=name_filters, limit_page_length=60):
		found[row.name] = (row, _rank(row.customer_name or "", txt))

	# ID match: CUST-2026-04635 or NetSuite ID.
	id_or = [["name", "like", f"%{txt}%"]]
	if "custom_netsuite_id" in fields:
		id_or.append(["custom_netsuite_id", "=", txt])
	for row in frappe.get_list("Customer", fields=fields, or_filters=id_or, limit_page_length=10):
		if row.name not in found:
			found[row.name] = (row, RANK_ID)

	ordered = sorted(
		found.values(),
		key=lambda x: (-x[1], cint_safe(x[0].disabled), len(x[0].customer_name or "")),
	)[:MAX_RESULTS]

	results = []
	for i, (row, rank) in enumerate(ordered):
		bits = ["Customer", row.name]
		if row.get("custom_ops_status"):
			bits.append(row.custom_ops_status)
		if row.get("custom_county"):
			bits.append(row.custom_county)
		if row.get("custom_open_cases"):
			bits.append(f"{row.custom_open_cases} open case(s)")
		if row.disabled:
			bits.append("Disabled")
		results.append(
			{
				"label": row.customer_name or row.name,
				"value": row.customer_name or row.name,
				"description": " · ".join(cstr(b) for b in bits),
				"route": ["Form", "Customer", row.name],
				# keep the order stable inside one rank band
				"index": rank * 10 - i,
				"type": "Customer",
			}
		)
	return results


def cint_safe(v) -> int:
	try:
		return int(v or 0)
	except (TypeError, ValueError):
		return 0


# ---------------------------------------------------------------------------
# Full search (Ctrl+G / "Search for ...") clean-up.
# The search itself is unchanged (it still matches customer names, item codes etc.);
# this only re-orders the groups and trims the columns shown for each result.
# ---------------------------------------------------------------------------

# Groups listed here come first, in this order; everything else follows in the
# order set in Global Search Settings.
GROUP_ORDER = ["Customer", "Issue", "Sales Order", "Sales Invoice", "Payment Entry", "Lead"]

# Columns to show instead of the raw indexed fields: (column label, fieldname).
# The record's title (e.g. the customer name) is already shown in the Name column.
SLIM_COLUMNS = {
	"Sales Order": [("Order No", "name"), ("Status", "status")],
	"Sales Invoice": [("Invoice No", "name"), ("Status", "status")],
	"Issue": [("Case No", "name"), ("Status", "status"), ("Stage", "custom_stage")],
}


@frappe.whitelist()
def global_search(text: str, start: int = 0, limit: int = 20, doctype: str = ""):
	from frappe.desk.doctype.global_search_settings.global_search_settings import (
		get_doctypes_for_global_search,
	)
	from frappe.utils.global_search import search

	results = search(text, start=start, limit=limit, doctype=doctype) or []

	settings_order = list(get_doctypes_for_global_search() or [])
	order = GROUP_ORDER + [d for d in settings_order if d not in GROUP_ORDER]
	pos = {d: i for i, d in enumerate(order)}
	results.sort(key=lambda r: pos.get(r.get("doctype"), len(order)))  # stable: keeps rank within a group

	for r in results:
		cols = SLIM_COLUMNS.get(r.get("doctype"))
		if not cols:
			continue
		try:
			meta = frappe.get_meta(r.doctype)
			fields = [f for _, f in cols if f == "name" or meta.has_field(f)]
			vals = frappe.db.get_value(r.doctype, r.name, fields, as_dict=True) or {}
			parts = []
			for label, f in cols:
				v = r.name if f == "name" else vals.get(f)
				if v:
					parts.append(f"{label} : {cstr(v)}")
			if parts:
				r["content"] = " ||| ".join(parts)
		except Exception:
			pass

	return results
