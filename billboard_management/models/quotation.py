import base64
from io import BytesIO

from dateutil.relativedelta import relativedelta

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
    title = fields.Text(string="Title", required=False, store=True)
    po = fields.Char(string="PO", required=False, store=True)

    sub_total = fields.Float(string='Sub total', compute='_compute_sub_cost')
    vat = fields.Float(string='VAT 18%', compute="vat_compute")
    amount_total = fields.Float(string='Grand Total', compute="compute_grand_total")

    sub_total_flight = fields.Float(string='Sub total', compute='_compute_sub_cost_flight')
    vat_flight = fields.Float(string='VAT 18%', compute="vat_compute_flight")
    amount_total_flight = fields.Float(string='Grand Total', compute="compute_grand_total_flight")

    sub_total_material = fields.Float(string='Sub total', compute='_compute_sub_cost_material')
    vat_material = fields.Float(string='VAT 18%', compute="vat_compute_material")
    amount_total_material = fields.Float(string='Grand Total', compute="compute_grand_total_material")

    sub_total_rental = fields.Float(string='Sub total', compute='_compute_sub_cost_rental')
    vat_rental = fields.Float(string='VAT 18%', compute="vat_compute_rental")
    amount_total_rental = fields.Float(string='Grand Total', compute="compute_grand_total_rental")

    sub_total_discount = fields.Float(string='Sub total', compute='_compute_sub_cost_discount')
    vat_discount = fields.Float(string='VAT 18%', compute="vat_compute_discount")
    amount_total_discount = fields.Float(string='Grand Total', compute="compute_grand_total_discount")

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
        confirmed_order_lines = []
        for line in self.billboard_quotation_line_ids:
            confirmed_order_lines.append((0, 0, {
                'billboard_id': line.billboard_id.id,
                'unit': line.unit,
                'faces': line.faces,
                'material_cost': line.material_cost,
                'flighting_cost': line.flighting_cost,
                'no_of_months': line.no_of_months,
                'rental_per_month': line.discount,
                'cost_subtotal': line.cost_subtotal,
            }))

        confirmed_order_vals = {
            'customer_id': self.customer_id.id,
            'title': self.title,
            'po': self.po,
            'state': 'confirmed',
            'date': fields.Date.today(),
            # 'payment_term': self.payment_term.id if self.payment_term_id else False,
            'confirmed_orders_line_ids': confirmed_order_lines,
        }

        self.env['confirmed.orders'].create(confirmed_order_vals)

        # Automatic Create Contract
        for line in self.billboard_quotation_line_ids:
            contract_vals = {
                'name': self.env['ir.sequence'].next_by_code('contract.sequence') or 'New',
                'billboard_id': line.billboard_id.id,
                'customer_id': self.customer_id.id,
                'source': self.name,
                'po': self.po,
                'start_date': fields.Date.today(),  # Assuming the start date is today, can be customized
                'end_date': fields.Date.today() + relativedelta(months=line.no_of_months),
                # Calculating based on the number of months in the invoice line
            }

            self.env['billboard.contract'].create(contract_vals)

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

    @api.depends('billboard_quotation_line_ids')
    def _compute_sub_cost_flight(self):
        # self.sub_amount = 0
        self.sub_total_flight = 0 + sum(line.flighting_cost for line in self.billboard_quotation_line_ids)

    @api.depends('sub_total_flight')
    def vat_compute_flight(self):
        for rec in self:
            rec.vat_flight = rec.sub_total_flight * 0.18

    @api.depends('sub_total_flight', 'vat_flight')
    def compute_grand_total_flight(self):
        for rec in self:
            rec.amount_total_flight = rec.sub_total_flight + rec.vat_flight

    @api.depends('billboard_quotation_line_ids')
    def _compute_sub_cost_material(self):
        # self.sub_amount = 0
        self.sub_total_material = 0 + sum(line.material_cost for line in self.billboard_quotation_line_ids)

    @api.depends('sub_total_material')
    def vat_compute_material(self):
        for rec in self:
            rec.vat_material = rec.sub_total_material * 0.18

    @api.depends('sub_total_material', 'vat_material')
    def compute_grand_total_material(self):
        for rec in self:
            rec.amount_total_material = rec.sub_total_material + rec.vat_material

    @api.depends('billboard_quotation_line_ids')
    def _compute_sub_cost_rental(self):
        # self.sub_amount = 0
        self.sub_total_rental = 0 + sum(line.rental_per_month for line in self.billboard_quotation_line_ids)

    @api.depends('sub_total_rental')
    def vat_compute_rental(self):
        for rec in self:
            rec.vat_rental = rec.sub_total_rental * 0.18

    @api.depends('sub_total_rental', 'vat_rental')
    def compute_grand_total_rental(self):
        for rec in self:
            rec.amount_total_rental = rec.sub_total_rental + rec.vat_rental

    @api.depends('billboard_quotation_line_ids')
    def _compute_sub_cost_discount(self):
        # self.sub_amount = 0
        self.sub_total_discount = 0 + sum(line.discount for line in self.billboard_quotation_line_ids)

    @api.depends('sub_total_discount')
    def vat_compute_discount(self):
        for rec in self:
            rec.vat_discount = rec.sub_total_discount * 0.18

    @api.depends('sub_total_discount', 'vat_discount')
    def compute_grand_total_discount(self):
        for rec in self:
            rec.amount_total_discount = rec.sub_total_discount + rec.vat_discount


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
    discount = fields.Float(string='Discount Price', default=0.0, store=True)
    cost_subtotal = fields.Float(string='Total Cost', compute='_cost_subtotal_compute')

    billboard_quotation_id = fields.Many2one(comodel_name="billboard.quotation", string="Billboard ID",
                                             required=False)

    @api.depends("unit", "faces", "flighting_cost", "discount", "material_cost", "no_of_months", "rental_per_month")
    def _cost_subtotal_compute(self):
        for rec in self:
            # Check if discount is not zero
            if rec.discount and rec.discount != 0:
                # Apply discount
                rec.cost_subtotal = (rec.faces * rec.no_of_months * rec.discount) + (
                        rec.material_cost + rec.flighting_cost)
            else:
                # Use the original formula without discount
                rec.cost_subtotal = (rec.faces * rec.no_of_months * rec.rental_per_month) + (
                        rec.material_cost + rec.flighting_cost)
