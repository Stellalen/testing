# Copyright Alitec (<http://alitec.sg>).
{
    'name': 'CRFG Print',
    'version': '14.00.00.17',
    'category': 'CRFG',
    'sequence': 60,
    'summary': '',
    'description': """
Customisation for 
==================================================
    - Last updated: 13-JUN-2021
    """,
    'author': 'Alitec Pte Ltd',
    'license': 'LGPL-3',
    'depends': ['base', 'crfg_operation', 'delivery', 'purchase_discount',
                ],
    'data': [
        'security/ir.model.access.csv',
        'reports/report.xml',
        'reports/purchase_quotation_templates.xml',
        'reports/purchase_report_templates.xml',
        'reports/report_stockpicking_operations.xml',
        'reports/report_deliveryslip.xml',
        'reports/report_purchaserequisition.xml',
        'reports/report_multiapproval_standard.xml',
        
    ],
    'test': [
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
