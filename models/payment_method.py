from odoo import models, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model_create_multi
    def create(self, vals_list):
        print('fhjbeivbjeij')
        for vals in vals_list:
            # If payment_method_line_id not provided
            if not vals.get('payment_method_line_id') and vals.get('journal_id'):

                journal = self.env['account.journal'].browse(vals['journal_id'])
                payment_type = vals.get('payment_type', 'inbound')

                if payment_type == 'inbound':
                    method_line = journal.inbound_payment_method_line_ids[:1]
                else:
                    method_line = journal.outbound_payment_method_line_ids[:1]

                if method_line:
                    vals['payment_method_line_id'] = method_line.id

        return super().create(vals_list)