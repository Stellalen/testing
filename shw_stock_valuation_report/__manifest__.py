{
    'name': 'Stock Valuation Report',
    'version': '14.0.0.0.3',
    'sequence': 1,
    'category': 'ShadowERP',
    'summary': 'Using this module you can Get stock valuation report in xlsx and pdf formate for any location or warehouse or date range',
    'description': """
            - Last Update: 28-JUL-2021
            - Using this module you can Get stock valuation report in xlsx and pdf formate,
                 for any location or warehouse or date range.""",
    "author" : "ShadowERP",
    "email": 'info.shadowerp@gmail.com',
    "website":'https://www.shadowerp.co.in',
    'license': 'OPL-1',
    'depends': ['stock','purchase','sale_stock'],
    'data': [
        'security/ir.model.access.csv',        
        'wizard/stock_valuation_wizard.xml',
        'wizard/excel_report_result_wizard.xml',
        'reports/report.xml',
        'reports/report_stock_valuation_template.xml',
    ],
    'demo': [],
    'test': [],
    'qweb': [],
    'images': ['static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': True,
}







