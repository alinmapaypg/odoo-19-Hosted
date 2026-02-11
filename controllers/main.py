# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hmac
import logging
import pprint
import logging
import requests
from odoo import fields, http, _
from odoo.http import request, route

import werkzeug
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.fields import Command
from odoo.http import request, route
from odoo.tools import SQL

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import hashlib
import json
from decimal import Decimal
from odoo.addons.website_sale.controllers.payment import PaymentPortal
from datetime import datetime

from odoo.exceptions import AccessError, UserError, ValidationError

from werkzeug.utils import redirect
from werkzeug.exceptions import Forbidden
import base64
from odoo import http
from psycopg2.errors import LockNotAvailable
from odoo.exceptions import ValidationError
from odoo.http import request


_logger = logging.getLogger(__name__)


class AlinmaController(http.Controller):
    _return_url = '/payment/alinma/return'
    _webhook_url = '/payment/alinma/webhook'

    @http.route(
        _return_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False
    )
    def alinma_return_from_checkout(self, **data):
        _logger.info("Handling redirection from Alinma with data:\n%s", pprint.pformat(data))
        provider = request.env['payment.provider'].sudo().search([('code','=','alinma')],limit=1)
        key_hex = provider.alinma_merchant_key
        if not key_hex:
            return "Configuration Error: Missing merchant key"

        key = bytes.fromhex(key_hex)
        encrypted_data = data.get('data')
        if not encrypted_data:
            return "Error: Missing encrypted data"

        encrypted_data = base64.b64decode(encrypted_data)
        cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

        # Unpad decrypted data
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        unpadded_data = unpadder.update(decrypted_data) + unpadder.finalize()
        decrypted_text = json.loads(unpadded_data.decode('utf-8'))

        user_data = {}
        additional_details = decrypted_text.get('additionalDetails')

        if additional_details and additional_details.get('userData'):
            try:
                user_data = json.loads(additional_details['userData'])
            except json.JSONDecodeError:
                _logger.error("Invalid userData JSON: %s", additional_details['userData'])

        reference = user_data.get('reference')
        order_info = decrypted_text.get('orderDetails', {})
        order_id = int(order_info.get('orderId', 0))
        notification_data = {
            'merchant_reference': reference,
            'status': decrypted_text.get('result'),
            'response_message': decrypted_text.get('responseDescription'),
            'provider_reference': decrypted_text.get('transactionId'),
        }
        # Check the integrity of the notification.
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('alinma', notification_data)

        tx_sudo._process_notification_data(notification_data)
        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='http', auth='public', methods=['POST'], csrf=False)
    def alinma_webhook(self, **data):
        _logger.info("Notification received from Alinma with data:\n%s", pprint.pformat(data))
        try:
            # Check the integrity of the notification.
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                'alinma', data
            )

            # Handle the notification data.
            tx_sudo._process_notification_data(data)
        except ValidationError:  # Acknowledge the notification to avoid getting spammed.
            _logger.exception("Unable to handle the notification data; skipping to acknowledge.")

        return ''  # Acknowledge the notification.