# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Payment Provider: AlinmaPay Payment Services",
    'version': '1.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': "An AlinmaPay payment provider",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'depends': ['payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_alinma_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'license': 'LGPL-3',
}
