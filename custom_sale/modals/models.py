import base64
import locale
from io import BytesIO

from odoo import fields, models, api


class AccountMoveInherit(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def company_info(self):
        company = self.env.user.company_id
        logo_data = base64.b64decode(company.logo)
        return {
            'name': company.name,
            'vat': company.vat,
            'regNo': company.company_registry,
            'street': company.street,
            'street2': company.street2,
            'city': company.city,
            'phone': company.phone,
            'email': company.email,
            'website': company.website,
            'logo': BytesIO(logo_data)
        }