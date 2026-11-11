app_name = "shalako_search"
app_title = "Shalako Search"
app_publisher = "Shalako Inc"
app_description = "Puts matching customers at the top of the ERPNext search bar"
app_email = "management@shalakoinc.com"
app_license = "mit"
required_apps = ["frappe", "erpnext"]

# Frappe 16: extra results for the Ctrl+K search bar (frappe.desk.search.awesomebar_search)
awesomebar_search = ["shalako_search.search.customer_results"]
