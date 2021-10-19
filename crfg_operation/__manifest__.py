# Copyright Alitec (<http://alitec.sg>).
{
    'name': 'CRFG Operations',
    'version': '14.00.00.26',
    'category': 'CRFG',
    'sequence': 60,
    'summary': '',
    'description': """
Customisation for 
==================================================
    - Last updated: 19-oct-2021
    """,
    'author': 'Alitec Pte Ltd',
    'license': 'LGPL-3',
    'depends': ['sale', 'purchase', 'stock', 'purchase_requisition', 'multi_level_approval_configuration'],
    'data': [
        'security/ir.model.access.csv',
        'security/operation_security.xml',
        'data/operation_data.xml',
        'views/purchase.xml',
        'views/stock.xml',
        'views/invoice.xml',
        'views/purchase_requisition.xml',
        'views/approval.xml',
    ],
    'test': [
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
