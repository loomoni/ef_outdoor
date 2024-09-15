{
    'name': 'Custom Sale',
    'version': '1.0',
    'category': 'sahe',
    'depends': ['base', 'sale', 'stock'],
    'data': [
        'views/report_stock_picking.xml',
        'reports/reports.xml',
        'reports/delivery_note.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/custom_sale/static/src/img/Logo.JPG',
        ],
    },
}
