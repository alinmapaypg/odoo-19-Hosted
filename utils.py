# Part of Odoo. See LICENSE file for full copyright and licensing details.

def get_payment_option(payment_method_code):
    return payment_method_code.upper() if payment_method_code != 'card' else ''
