from . import __version__ as app_version
app_name = "erpnextkta"
app_title = "erpnextkta"
app_publisher = "Framras AS"
app_description = "KTA Endustri ozellestirmeleri CERKEZKOY TURKIYE"
app_email = "bilgi@framras.com.tr"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "erpnextkta",
# 		"logo": "/assets/erpnextkta/logo.png",
# 		"title": "erpnextkta",
# 		"route": "/erpnextkta",
# 		"has_permission": "erpnextkta.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpnextkta/css/erpnextkta.css"
# app_include_js = "/assets/erpnextkta/js/erpnextkta.js"
app_include_js = ["assets/erpnextkta/js/stock_entry_get_items_from_calisma_karti.js",
                  "assets/erpnextkta/js/material_transfer_patch.js"
]

# include js, css files in header of web template
# web_include_css = "/assets/erpnextkta/css/erpnextkta.css"
# web_include_js = "/assets/erpnextkta/js/erpnextkta.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erpnextkta/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "erpnextkta/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "erpnextkta.utils.jinja_methods",
# 	"filters": "erpnextkta.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "erpnextkta.install.before_install"
# after_install = "erpnextkta.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "erpnextkta.uninstall.before_uninstall"
# after_uninstall = "erpnextkta.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "erpnextkta.utils.before_app_install"
# after_app_install = "erpnextkta.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "erpnextkta.utils.before_app_uninstall"
# after_app_uninstall = "erpnextkta.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnextkta.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
    "Purchase Receipt": "erpnextkta.overrides.KTAPurchaseReceipt.KTAPurchaseReceipt",
    "Quality Inspection": "erpnextkta.overrides.KTAQualityInspection.KTAQualityInspection",
    "BOM": "erpnextkta.overrides.KTAbom.KTAbom",
    "Purchase Order": "erpnextkta.overrides.KTAPurchaseOrder.KTAPurchaseOrder",
    "Stock Reconciliation": "erpnextkta.overrides.stock_reconciliation.StockReconciliation"
}
doc_events = {
    "Kalite Kontrol": {
        "on_submit": "erpnextkta.erpnextkta.doctype.calisma_karti.calisma_karti.qc_on_submit"
    },
    "Job Card": {
        "on_update": "erpnextkta.overrides.job_card_status.update_work_order_status"
    },
    "Stock Reconciliation": {
        "on_update": "erpnextkta.kta_stock.realtime.stock_reco_dashboard.on_update",
        "on_cancel": "erpnextkta.kta_stock.realtime.stock_reco_dashboard.on_update",
        "on_trash": "erpnextkta.kta_stock.realtime.stock_reco_dashboard.on_update",
    },
}
# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
# 	"all": [
# 		"erpnextkta.tasks.all"
# 	],
# 	"daily": [
# 		"erpnextkta.tasks.daily"
# 	],
# 	"hourly": [
# 		"erpnextkta.tasks.hourly"
# 	],
    "weekly": [
        "erpnextkta.tasks.weekly"
    ],
# 	"monthly": [
# 		"erpnextkta.tasks.monthly"
# 	],
}

# Testing
# -------

# before_tests = "erpnextkta.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erpnextkta.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "erpnextkta.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["erpnextkta.utils.before_request"]
# after_request = ["erpnextkta.utils.after_request"]

# Job Events
# ----------
# before_job = ["erpnextkta.utils.before_job"]
# after_job = ["erpnextkta.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"erpnextkta.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Fixtures
# --------------------------------

fixtures = [
    "KTA Olcu Metodu",
#    "TR Gumruk ve Dis Ticaret Bolge Mudurlukleri",
#    "TR Gumruk Idareleri",
#    "Asset Category",
#    "KTA Ithalat Kisa Malzeme Aciklamalari",
    "Customs Tariff Number",
    {
        "doctype": "Client Script",
        "filters": [
            ["name", "like", "KTA%"]
        ]
    }
]
doctype_js = {
    "Calisma Karti": "erpnextkta/kta_calisma_karti/doctype/calisma_karti/calisma_karti.js",
    "Stock Reconciliation": "public/js/stock_reconciliation.js"
}
