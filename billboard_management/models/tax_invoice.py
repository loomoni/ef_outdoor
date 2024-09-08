import base64
from io import BytesIO

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api


class TaxInvoice(models.Model):
    _name = 'tax.invoice'
    _description = 'Tax Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char(string='Reference No', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: 'New')

    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    date = fields.Date(string='Date', required=True)
    payment_term = fields.Many2one(comodel_name="account.payment.term", string='Payment Terms', required=False)
    sub_total = fields.Float(string='Sub total', compute='_compute_sub_cost')
    vat = fields.Float(string='VAT 18%', compute="vat_compute")
    amount_total = fields.Float(string='Grand Total', compute="compute_grand_total")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

    tax_invoice_line_ids = fields.One2many(comodel_name="tax.invoice.line",
                                           inverse_name="tax_invoice_id",
                                           string="Invoice Line Id",
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
            vals['name'] = self.env['ir.sequence'].next_by_code('tax.invoice') or 'New'
        return super(TaxInvoice, self).create(vals)

    def action_send_quotation(self):
        self.state = 'sent'
        # Logic to send the quotation to the customer (email template, etc.)

    def action_confirm_invoice(self):
        self.state = 'confirmed'

        # Create contract for each billboard in the invoice lines
        for line in self.tax_invoice_line_ids:
            contract_vals = {
                'name': self.env['ir.sequence'].next_by_code('contract.sequence') or 'New',
                'billboard_id': line.billboard_id.id,
                'customer_id': self.customer_id.id,
                'start_date': fields.Date.today(),  # Assuming the start date is today, can be customized
                'end_date': fields.Date.today() + relativedelta(months=line.no_of_months),
                # Calculating based on the number of months in the invoice line
            }

            self.env['billboard.contract'].create(contract_vals)

        # Create an account.move (invoice) record
        move_vals = {
            'move_type': 'out_invoice',  # Assuming it's a customer invoice (sale type)
            'partner_id': self.customer_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': self.date,  # Due date as per your `date` field or a payment term
            'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,
            'invoice_origin': self.name,
            # Get default sales journal
            'invoice_line_ids': [(0, 0, {
                'product_id': 7,  # Assuming you have product in billboard
                'name': line.billboard_id.name or 'Billboard service',
                'quantity': 1,
                'price_unit': self.sub_total,  # Assuming price from rental per month
                # 'tax_ids': 1,
                'tax_ids': [(6, 0, [self.env['account.tax'].search([('amount', '=', 18), ('type_tax_use', '=', 'sale')], limit=1).id])],
                'account_id': self.env['account.account'].search([('user_type_id.type', '=', 'income')], limit=1).id,
            }) for line in self.tax_invoice_line_ids]  # Create an invoice line for each line in the tax invoice
        }

        # Create the account.move entry
        move = self.env['account.move'].create(move_vals)

        # Optionally, post the invoice automatically
        move.action_post()

        return move  # Return the created move if needed

        # Automatically create a contract upon confirmation
        # self.env['billboard.contract'].create({
        #     'billboard_id': self.billboard_id.id,
        #     'customer_id': self.customer_id.id,
        #     'start_date': self.start_date,
        #     'end_date': self.end_date,
        #     'rental_price': self.rental_price,
        # })

    def action_cancel_quotation(self):
        self.state = 'cancelled'

    @api.depends('tax_invoice_line_ids')
    def _compute_sub_cost(self):
        # self.sub_amount = 0
        self.sub_total = 0 + sum(line.cost_subtotal for line in self.tax_invoice_line_ids)

    @api.depends('sub_total')
    def vat_compute(self):
        for rec in self:
            rec.vat = rec.sub_total * 0.18

    @api.depends('sub_total', 'vat')
    def compute_grand_total(self):
        for rec in self:
            rec.amount_total = rec.sub_total + rec.vat


class TaxInvoiceLines(models.Model):
    _name = 'tax.invoice.line'
    _description = 'Tax Invoice Line'

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
    cost_subtotal = fields.Float(string='Total Cost', compute='_cost_subtotal_compute')

    tax_invoice_id = fields.Many2one(comodel_name="tax.invoice", string="Billboard ID",
                                     required=False)

    @api.depends("unit", "faces", "flighting_cost", "material_cost", "no_of_months", "rental_per_month")
    def _cost_subtotal_compute(self):
        for rec in self:
            # rec.cost_subtotal = rec.unit * rec.faces * \
            #                     (rec.material_cost if rec.material_cost != 0 else 1) * \
            #                     (rec.flighting_cost if rec.flighting_cost != 0 else 1) * \
            #                     (rec.no_of_months if rec.no_of_months != 0 else 1) * \
            #                     (rec.rental_per_month if rec.rental_per_month != 0 else 1)

            rec.cost_subtotal = rec.unit * rec.faces * (
                    rec.material_cost + rec.flighting_cost + rec.no_of_months + rec.rental_per_month)
