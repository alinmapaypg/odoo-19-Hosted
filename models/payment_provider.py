# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import logging
from odoo import fields, models
from odoo.addons.payment_alinmapay import const
import json

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('alinma', "AlinmaPay Payment Services")], ondelete={'alinma': 'set default'}
    )

    alinma_name = fields.Char('Name', required_if_provider='alinma',)
    alinma_terminal_id = fields.Char('Terminal Id', required_if_provider='alinma',)
    alinma_terminal_password = fields.Char('Terminal Password', required_if_provider='alinma',)
    alinma_merchant_key = fields.Char('Merchant Key', required_if_provider='alinma',)
    alinma_url = fields.Char('URL', required_if_provider='alinma',)

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        self.ensure_one()
        if self.code != 'alinma':
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _alinma_get_api_url(self):
        if self.state == 'enabled':
            return self.alinma_url

    def _alinma_calculate_signature(self, data, incoming=True):
        """
            Hashes the data dictionary using SHA-256.

            Overrider the base function.
            """
        # 1. Convert dict to a JSON string (ensuring keys are sorted for consistency)
        data_string = json.dumps(data, sort_keys=True, separators=(',', ':'))

        # 2. Combine with your Secret Key (Salt)
        # Most gateways use: SecretKey + Data or Data + SecretKey
        signing_string = f"{data_string}"

        # 3. Generate SHA-256 Hex Digest
        return hashlib.sha256(signing_string.encode('utf-8')).hexdigest()

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'alinma':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES
