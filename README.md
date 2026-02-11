# AlinmaPay Payment Gateway for Odoo

This module integrates **AlinmaPay Payment Gateway** with **Odoo 19**, allowing merchants to securely accept online payments through the Odoo e-Commerce platform.

---

## Overview

Odoo is a powerful open-source e-Commerce platform that enables merchants to build and manage online stores with extensive customization options.
By integrating AlinmaPay, merchants can process payments securely and efficiently within the Odoo checkout flow.

---

## Compatibility

| Component   | Version |
|------------|---------|
| Odoo       | 19.0    |
| PostgreSQL | 15.13   |

---

## Prerequisites

Before installing the module, ensure the following:

- A registered **AlinmaPay Merchant account**
- Access to the **Merchant Dashboard**
- Valid merchant credentials issued by AlinmaPay

### Required Merchant Credentials

| Attribute | Description |
|---------|-------------|
| Terminal ID | Unique terminal identifier issued to the merchant |
| Terminal Password | Secure password for the terminal |
| Merchant Key | Secret key used for request & response hashing |
| Service URL | Payment Gateway API endpoint |

---

## Installation Steps

1. Extract the provided source code.
2. Copy the module directory into the Odoo addons path  
   *(e.g. `C:\Program Files\Odoo 19.0\server\odoo\addons`)*.
3. Restart Odoo services.
4. Log in to Odoo as an administrator.
5. Navigate to **Apps → Update Apps List**.
6. Search for **AlinmaPay Payment Gateway**.
7. Install and activate the module.

---

## Configuration

1. Go to **Accounting → Configuration → Payment Providers**.
2. Open **AlinmaPay**.
3. Enter:
   - Terminal ID
   - Terminal Password
   - Merchant Key
4. Save the configuration.

> ⚠️ Merchant Key is confidential and must never be shared.

---

## Checkout & Payment Flow

1. Go to **Website → Cart**
2. Click **Checkout**
3. Click **Pay**
4. Redirects to **AlinmaPay Payment Page**
5. Complete payment
6. Order status updates automatically in Odoo

---

## Supported Payment Methods

- Purchase

---

## API Specifications

Detailed request/response formats and response codes are available in the Merchant Portal:

**Developer → API Keys → Developer Integration Guide**

---

## Author & Document History

- Prepared by: AlinmaPay Integration Team
- Document Version: 3.0

---

## License

LGPL-3
