# -*- coding: utf-8 -*-
{
    'name': 'weighing_reception',
    'version': '16',
    'category': 'Purchase',
    'summary': '____',
    'description': """""",
    'author': 'Grupo Quanam Colombia SAS',
    'maintainer': '',
    'website': '',
    'depends': ['base', 'purchase', 'stock', 'hr', 'agriculture_management_odoo'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/weighing_reception_views.xml',
        'report/weighing_reception_report.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'AGPL-3',
}