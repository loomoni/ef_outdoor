import base64
from io import BytesIO

from odoo import models, fields, api


class BillboardQuotation(models.Model):
    _name = 'billboard.quotation'
    _description = 'Billboard Quotation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char(string='Quotation Reference', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: 'New')

    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    date = fields.Date(string='Date', required=True)

    sub_total = fields.Float(string='Sub total', compute='_compute_sub_cost')
    vat = fields.Float(string='VAT 18%', compute="vat_compute")
    amount_total = fields.Float(string='Grand Total', compute="compute_grand_total")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

    billboard_quotation_line_ids = fields.One2many(comodel_name="billboard.quotation.line",
                                                   inverse_name="billboard_quotation_id",
                                                   string="Billboard Line Id",
                                                   required=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft')

    # @api.model
    # def company_info(self):
    #     # Access the company of the current user
    #     company = self.env.user.company_id
    #
    #     # Ensure the logo is base64-encoded and decode it if it exists
    #     logo_data = base64.b64decode(company.logo) if company.logo else None
    #
    #     # Return company info including logo
    #     return {
    #         'name': company.name,
    #         'vat': company.vat,
    #         'regNo': company.company_registry,
    #         'street': company.street,
    #         'street2': company.street2,
    #         'city': company.city,
    #         'phone': company.phone,
    #         'email': company.email,
    #         'website': company.website,
    #         'logo': BytesIO(logo_data) if logo_data else None,  # Handle cases where logo might not exist
    #     }

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

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('billboard.quotation') or 'New'
        return super(BillboardQuotation, self).create(vals)

    def action_send_quotation(self):
        self.state = 'sent'
        # Logic to send the quotation to the customer (email template, etc.)

    def action_confirm_quotation(self):
        self.state = 'confirmed'

        # Create tax invoice
        tax_invoice_lines = []
        for line in self.billboard_quotation_line_ids:
            tax_invoice_lines.append((0, 0, {
                'billboard_id': line.billboard_id.id,
                'unit': line.unit,
                'faces': line.faces,
                'material_cost': line.material_cost,
                'flighting_cost': line.flighting_cost,
                'no_of_months': line.no_of_months,
                'rental_per_month': line.rental_per_month,
                'cost_subtotal': line.cost_subtotal,
            }))

        tax_invoice_vals = {
            'customer_id': self.customer_id.id,
            'state': 'confirmed',
            'date': fields.Date.today(),
            # 'payment_term': self.payment_term.id if self.payment_term_id else False,
            'tax_invoice_line_ids': tax_invoice_lines,
        }

        self.env['tax.invoice'].create(tax_invoice_vals)


        # Automatically create a contract upon confirmation
        # self.env['billboard.contract'].create({
        #     'billboard_id': self.billboard_id.id,
        #     'customer_id': self.customer_id.id,
        #     'start_date': self.start_date,
        #     'end_date': self.end_date,
        #     'rental_price': self.rental_price,
        # })

        # self.env['billboard.contract'].create({
        #     'billboard_id': self.billboard_id.id,
        #     'customer_id': self.customer_id.id,
        #     'start_date': self.start_date,
        #     'end_date': self.end_date,
        #     'rental_price': self.rental_price,
        # })

    def action_cancel_quotation(self):
        self.state = 'cancelled'

    @api.depends('billboard_quotation_line_ids')
    def _compute_sub_cost(self):
        # self.sub_amount = 0
        self.sub_total = 0 + sum(line.cost_subtotal for line in self.billboard_quotation_line_ids)

    @api.depends('sub_total')
    def vat_compute(self):
        for rec in self:
            rec.vat = rec.sub_total * 0.18

    @api.depends('sub_total', 'vat')
    def compute_grand_total(self):
        for rec in self:
            rec.amount_total = rec.sub_total + rec.vat


class BillboardQuotationLines(models.Model):
    _name = 'billboard.quotation.line'
    _description = 'Billboard Quotation Line'

    # billboard_id = fields.Many2one('billboard.management', string='Billboard', required=True)
    billboard_id = fields.Many2one(
        'billboard.management',
        string='Billboard',
        required=True,
        domain=[('availability', '=', 'available')]  # Domain to filter only available billboards
    )
    unit = fields.Integer(string='Units', required=False)
    faces = fields.Integer(string='Faces', required=False)
    flighting_cost = fields.Float(string='Flighting Cost', required=False)
    material_cost = fields.Float(string='Material Cost', required=False)
    no_of_months = fields.Integer(string='No of Month', required=False)
    rental_per_month = fields.Float(string='Rental Price')
    cost_subtotal = fields.Float(string='Total Cost', compute='_cost_subtotal_compute')

    billboard_quotation_id = fields.Many2one(comodel_name="billboard.quotation", string="Billboard ID",
                                             required=False)

    @api.depends("unit", "faces", "flighting_cost", "material_cost", "no_of_months", "rental_per_month")
    def _cost_subtotal_compute(self):
        for rec in self:
            # rec.cost_subtotal = rec.unit * rec.faces * \
            #                     (rec.material_cost if rec.material_cost != 0 else 1) * \
            #                     (rec.no_of_months if rec.no_of_months != 0 else 1) * \
            #                     (rec.rental_per_month if rec.rental_per_month != 0 else 1)
            rec.cost_subtotal = rec.unit * (rec.faces if rec.faces != 0 else 1) * rec.no_of_months * (
                        rec.material_cost + rec.flighting_cost + rec.rental_per_month)
            # if rec.unit > 0: rec.cost_subtotal = rec.unit * rec.faces * (rec.material_cost + 1) * (rec.no_of_months
            # + 1) * (rec.rental_per_month +1) else: rec.cost_subtotal = rec.faces * rec.material_cost *
            # rec.no_of_months * rec.rental_per_month
