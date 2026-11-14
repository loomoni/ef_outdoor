{
    'name': 'Expense Check Number',
    'version': '15.0.1.2.0',
    'license': 'LGPL-3',
    'summary': 'Add check number to expense sheet',
    'category': 'Human Resources',
    'author': 'Your Name',
    'depends': ['hr_expense', 'account'],
    'data': [
        'views/hr_expense_sheet_view.xml',
    ],
    'installable': True,
    'application': False,
}
