# Part of Odoo. See LICENSE file for full copyright and licensing details.
from werkzeug import urls
from odoo import _, api, models
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_alinmapay.controllers.main import AlinmaController
import logging
import requests
from odoo import fields, http, _
from odoo.http import request, route
import hashlib
import json
from decimal import Decimal
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _compute_reference(self, provider_code, prefix=None, separator='-', **kwargs):
        if provider_code == 'alinma':
            prefix = payment_utils.singularize_reference_prefix()

        return super()._compute_reference(provider_code, prefix=prefix, separator=separator, **kwargs)

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'alinma':
            return res
        base_url = self.provider_id.get_base_url()
        order = self.sale_order_ids
        num = Decimal(str(order.amount_total))
        formatted_num = num.quantize(Decimal('0.01'))
        terminal_id = self.provider_id.alinma_terminal_id
        terminal_password = self.provider_id.alinma_terminal_password
        merchant_key = self.provider_id.alinma_merchant_key
        url = self.provider_id.alinma_url
        if not terminal_id or not terminal_password or not merchant_key or not merchant_key:
            return ValidationError('Credentials Mismatch')
        data = str(order.id) + '|' + terminal_id + '|' + terminal_password + '|' + merchant_key + '|' + str(
            formatted_num) + '|' + 'SAR'
        hash_object = hashlib.sha256()
        hash_object.update(data.encode('utf-8'))
        hash_key = hash_object.hexdigest()
        rendering_values = {
            'command': 'PURCHASE',
            'access_code': self.provider_id.alinma_merchant_key,
            'merchant_identifier': self.provider_id.alinma_merchant_key,
            'amount': str(num),
            'currency': 'SAR',
            'language': self.partner_lang[:2],
            'customer_email': self.partner_id.email_normalized,
            'return_url': urls.url_join(base_url, AlinmaController._return_url),
        }
        user_data = {
            "entryone": "abc",
            "entrytwo": "def",
            "entrythree": "xyz",
            "receiptUrl": f"{request.httprequest.host_url}payment/alinma/return",
            "reference": self.reference,
        }
        data = {
            "terminalId": terminal_id,
            "password": terminal_password,
            "signature": str(hash_key),
            "paymentType": "1",
            "amount": str(formatted_num),
            "currency": 'SAR', "order": {
                "orderId": str(order.id),
                "description": self.reference,
            },
            "customer": {
                "customerEmail": order.partner_id.email if order.partner_id.email else '',
                "billingAddressStreet": order.partner_id.street if order.partner_id.street else '',
                "billingAddressCity": order.partner_id.city if order.partner_id.city else '',
                "billingAddressState": order.partner_id.state_id.name if order.partner_id.state_id else '',
                "billingAddressPostalCode": order.partner_id.zip if order.partner_id.zip else '',
                "billingAddressCountry": order.partner_id.country_id.code if order.partner_id.country_id else '',
            },
            "additionalDetails": {
                "userData": json.dumps(user_data)
            }
        }
        headers = {
            "Content-Type": "application/json",
        }
        _logger.info(data)
        response = requests.post(url, json=data, headers=headers)
        _logger.info(response)
        if response.status_code == 200:
            result = response.json()
            external_url = f"{result.get('paymentLink').get('linkUrl')}{result.get('transactionId')}"
            _logger.info(external_url)
            rendering_values.update({
                'signature': self.provider_id._alinma_calculate_signature(
                    rendering_values, incoming=False
                ),
                'api_url': external_url,
            })
        return rendering_values


    def _get_tx_from_notification_data(self, provider_code, notification_data):
        if provider_code != 'alinma':
            pass
            # return tx

        reference = notification_data.get('merchant_reference')
        if not reference:
            raise ValidationError(
                "Alinma: " + _("Received data with missing reference %(ref)s.", ref=reference)
            )

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'alinma')])
        if not tx:
            raise ValidationError(
                "Alinma: " + _("No transaction found matching reference %s.", reference)
            )

        return tx

    def _process_notification_data(self, notification_data):
        if self.provider_code != 'alinma':
            return

        # Update the provider reference.
        self.provider_reference = notification_data.get('provider_reference')

        # Update the payment method.
        payment_option = 'card'
        payment_method = self.env['payment.method']._get_from_code(payment_option.lower())
        self.payment_method_id = payment_method or self.payment_method_id
        #
        # # Update the payment state.
        status = notification_data.get('status')
        if not status:
            raise ValidationError("ALinma: " + _("Received data with missing payment state."))
        if status != 'SUCCESS':
            self._set_error(_(
                "Transaction Failed, Please try again later."))
        elif status == 'SUCCESS':
            self._set_done()
            self.sale_order_ids.action_confirm()
            return request.redirect('/shop/confirmation')
        else:  # Classify unsupported payment state as `error` tx state.
            status_description = notification_data.get('response_message')
            _logger.info(
                "Received data with invalid payment status (%(status)s) and reason '%(reason)s' "
                "for transaction with reference %(ref)s",
                {'status': status, 'reason': status_description, 'ref': self.reference},
            )
            self._set_error("Alinma: " + _(
                "Received invalid transaction status %(status)s and reason '%(reason)s'.",
                status=status, reason=status_description
            ))

    def _create_payment(self, **extra_create_values):
        """Create an `account.payment` record for the current transaction.

        If the transaction is linked to some invoices, their reconciliation is done automatically.

        Note: self.ensure_one()

        :param dict extra_create_values: Optional extra create values
        :return: The created payment
        :rtype: recordset of `account.payment`
        """
        self.ensure_one()

        reference = f'{self.reference} - {self.provider_reference or ""}'

        payment_method_line = self.provider_id.journal_id.inbound_payment_method_line_ids\
            .filtered(lambda l: l.payment_provider_id == self.provider_id)
        if not payment_method_line:
            payment_method_line = self.provider_id.journal_id.inbound_payment_method_line_ids[:1]
        print(payment_method_line)
        payment_values = {
            'amount': abs(self.amount),  # A tx may have a negative amount, but a payment must >= 0
            'payment_type': 'inbound' if self.amount > 0 else 'outbound',
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.commercial_partner_id.id,
            'partner_type': 'customer',
            'journal_id': self.provider_id.journal_id.id,
            'company_id': self.provider_id.company_id.id,
            'payment_method_line_id': payment_method_line.id,
            'payment_token_id': self.token_id.id,
            'payment_transaction_id': self.id,
            'memo': reference,
            'write_off_line_vals': [],
            'invoice_ids': self.invoice_ids,
            **extra_create_values,
        }

        for invoice in self.invoice_ids:
            if invoice.state != 'posted':
                continue
            next_payment_values = invoice._get_invoice_next_payment_values()
            if next_payment_values['installment_state'] == 'epd' and self.amount == next_payment_values['amount_due']:
                aml = next_payment_values['epd_line']
                epd_aml_values_list = [({
                    'aml': aml,
                    'amount_currency': -aml.amount_residual_currency,
                    'balance': -aml.balance,
                })]
                open_balance = next_payment_values['epd_discount_amount']
                early_payment_values = self.env['account.move']._get_invoice_counterpart_amls_for_early_payment_discount(epd_aml_values_list, open_balance)
                for aml_values_list in early_payment_values.values():
                    if (aml_values_list):
                        aml_vl = aml_values_list[0]
                        aml_vl['partner_id'] = invoice.partner_id.id
                        payment_values['write_off_line_vals'] += [aml_vl]
                break

        payment_term_lines = self.invoice_ids.line_ids.filtered(lambda line: line.display_type == 'payment_term')
        if payment_term_lines:
            payment_values['destination_account_id'] = payment_term_lines[0].account_id.id

        payment = self.env['account.payment'].create(payment_values)
        payment.action_post()

        # Track the payment to make a one2one.
        self.payment_id = payment

        # Reconcile the payment with the source transaction's invoices in case of a partial capture.
        if self.operation == self.source_transaction_id.operation:
            invoices = self.source_transaction_id.invoice_ids
        else:
            invoices = self.invoice_ids
        invoices = invoices.filtered(lambda inv: inv.state != 'cancel')
        if invoices:
            invoices.filtered(lambda inv: inv.state == 'draft').action_post()

            (payment.move_id.line_ids + invoices.line_ids).filtered(
                lambda line: line.account_id == payment.destination_account_id
                and not line.reconciled
            ).reconcile()

        return payment
