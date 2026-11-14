{
    'name': 'Expense Check Number',
    'version': '15.0.1.1.0',
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
