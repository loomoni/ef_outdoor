import base64
from io import BytesIO

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api
from odoo.exceptions import ValidationError, _logger, UserError


class ConfirmedOrders(models.Model):
    _name = 'confirmed.orders'
    _description = 'Confirmed Orders'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char(string='Reference No', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: 'New')
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    date = fields.Date(string='Date', required=True)
    payment_term = fields.Many2one(comodel_name="account.payment.term", string='Payment Terms', required=False)
    sub_total = fields.Float(string='Sub total', compute='_compute_sub_cost', store=True)
    vat = fields.Float(string='VAT 18%', compute="vat_compute", store=True)
    amount_total = fields.Float(string='Grand Total', compute="compute_grand_total", store=True)
    amount_due = fields.Float(string='Amount Due', compute="_compute_total_amount_due", store=True)
    total_amount_paid = fields.Float(string='Total Paid', compute="compute_total_amount_paid", store=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

    confirmed_orders_line_ids = fields.One2many(comodel_name="confirmed.orders.line",
                                                inverse_name="confirmed_orders_id",
                                                string="Orders Line Id",
                                                required=False)
    # move_ids = fields.One2many('account.move', 'invoice_origin', string='Account Moves')
    move_ids = fields.One2many(
        'account.move',  # Related model
        'invoice_origin',  # Field in account.move that refers to tax.invoice (must be Char)
        string='Account Moves',
        domain="[('invoice_origin', '=', name)]"  # Ensure domain compares strings
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('confirmed', 'Confirmed'),
        ('partial', 'Partial Paid'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('confirmed.orders') or 'New'
        return super(ConfirmedOrders, self).create(vals)

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

    @api.depends('confirmed_orders_line_ids')
    def _compute_sub_cost(self):
        # self.sub_amount = 0
        self.sub_total = 0 + sum(line.cost_subtotal for line in self.confirmed_orders_line_ids)

    @api.depends('sub_total')
    def vat_compute(self):
        for rec in self:
            rec.vat = rec.sub_total * 0.18

    @api.depends('sub_total', 'vat')
    def compute_grand_total(self):
        for rec in self:
            rec.amount_total = rec.sub_total + rec.vat

    def compute_total_amount_paid(self):
        for record in self:
            # Search for all account.move records where invoice_origin matches the name in tax.invoice
            account_moves = self.env['account.move'].search([('invoice_origin', '=', record.name)])

            # Sum the relevant amount (either amount_total, amount_residual, or another field)
            total_paid = sum(
                move.amount_total for move in account_moves)  # Amount paid = Total - Residual

            # Update the total_amount_paid in tax.invoice
            record.total_amount_paid = total_paid

    @api.depends('amount_total', 'total_amount_paid')
    def _compute_total_amount_due(self):
        for record in self:
            record.amount_due = record.amount_total - record.total_amount_paid
            if record.amount_due == 0:
                record.state = 'paid'
            elif 0 < record.amount_due < record.amount_total:
                record.state = 'partial'
            # else:
                record.state = 'confirmed'

    @api.depends('name')
    def action_create_invoice(self):
        if self.amount_due == 0:
            raise UserError('Cannot create an invoice for an order with 0 amount due.')

        # Prepare the invoice line data
        invoice_lines = []
        for line in self.confirmed_orders_line_ids:
            invoice_lines.append((0, 0, {
                'billboard_id': line.billboard_id.id,
                'unit': line.unit,
                'faces': line.faces,
                'material_cost': line.material_cost,
                'flighting_cost': line.flighting_cost,
                'no_of_months': line.no_of_months,
                'rental_per_month': line.rental_per_month,
                'cost_subtotal': line.cost_subtotal,
            }))

        # Create the tax invoice with its lines in one go
        invoice_vals = {
            'customer_id': self.customer_id.id,
            'source': self.name,
            'state': 'draft',
            'date': fields.Date.today(),
            'sub_total': self.sub_total,
            'tax_invoice_line_ids': invoice_lines,  # Add the invoice lines here
        }

        tax_invoice = self.env['tax.invoice'].create(invoice_vals)

        # Open the created invoice in form view
        return {
            'name': 'Tax Invoice',
            'type': 'ir.actions.act_window',
            'res_model': 'tax.invoice',
            'view_mode': 'form',
            'res_id': tax_invoice.id,
            'target': 'current',
        }


class TaxInvoiceLines(models.Model):
    _name = 'confirmed.orders.line'
    _description = 'Confirmed Orders Line'

    # billboard_id = fields.Many2one('billboard.management', string='Billboard', required=True)
    billboard_id = fields.Many2one(
        'billboard.management',
        string='Billboard',
        required=True,
        domain=[('availability', '=', 'available')]  # Domain to filter only available billboards
    )
    unit = fields.Integer(string='Units', required=False)
    faces = fields.Integer(string='Faces', required=False)
    material_cost = fields.Float(string='Material Cost', required=False)
    flighting_cost = fields.Float(string='Flighting Cost', required=False)
    no_of_months = fields.Integer(string='No of Month', required=False)
    rental_per_month = fields.Float(string='Rental Price')
    cost_subtotal = fields.Float(string='Total Cost', compute='_cost_subtotal_compute', store=True)

    confirmed_orders_id = fields.Many2one(comodel_name="confirmed.orders", string="Billboard ID",
                                          required=False)

    @api.depends("unit", "faces", "flighting_cost", "material_cost", "no_of_months", "rental_per_month")
    def _cost_subtotal_compute(self):
        for rec in self:
            rec.cost_subtotal = (rec.faces * rec.no_of_months * rec.rental_per_month) + (
                    rec.material_cost + rec.flighting_cost)
            # rec.cost_subtotal = rec.unit * (rec.faces if rec.faces != 0 else 1) * rec.no_of_months * (
            #         rec.material_cost + rec.flighting_cost + rec.rental_per_month)
