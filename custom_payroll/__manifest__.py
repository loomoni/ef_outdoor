# -*- coding: utf-8 -*-
{
    'name': "EF Custom Payroll",

    'summary': """
        Custom Payroll""",

    'description': """
        Custom Payroll
    """,

    'author': "Loomoni Morwo",
    'website': "https://kalen.co.tz/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'payroll',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'hr_payroll_community', 'hr_payroll_account_community', 'hr_expense', 'purchase'],

    # always loaded
    'data': [

        'security/security.xml',
        'security/ir.model.access.csv',
        'views/payroll_summary.xml',
        'views/expenses_view.xml',
    ],

    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
