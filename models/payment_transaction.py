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
            formatted_num) + '|' + self.currency_id.name
        hash_object = hashlib.sha256()
        hash_object.update(data.encode('utf-8'))
        hash_key = hash_object.hexdigest()
        rendering_values = {
            'command': 'PURCHASE',
            'access_code': self.provider_id.alinma_merchant_key,
            'merchant_identifier': self.provider_id.alinma_merchant_key,
            'amount': str(num),
            'currency': self.currency_id.name,
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
            "currency": self.currency_id.name, "order": {
                "orderId": str(order.id),
                "description": self.reference,
            },
            "customer": {
                "customerEmail": "merchant.autouser@concertosoft.com",
                "billingAddressStreet": "101 Mahape",
                "billingAddressCity": "Mumbai",
                "billingAddressState": "Maharashtra",
                "billingAddressPostalCode": "400709",
                "billingAddressCountry": "IN"
            },
            "additionalDetails": {
                "userData": json.dumps(user_data)
            }
        }
        headers = {
            "Content-Type": "application/json",
        }
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            result = response.json()
            external_url = f"{result.get('paymentLink').get('linkUrl')}{result.get('transactionId')}"
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
                "An error occurred during the processing of your payment, "
                "Please try again."))
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