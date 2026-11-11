# Shalako Search

Adds matching **Customers** to the top of the ERPNext search bar (Ctrl+K), ranked by how
closely the name matches what was typed. Uses Frappe 16's `awesomebar_search` hook.

Matches on customer name (every word typed must appear), customer ID (CUST-…) and the
NetSuite ID. Exact and starts-with matches rank first. Respects user permissions.
