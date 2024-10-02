import base64
from io import BytesIO

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api
from odoo.exceptions import ValidationError, _logger, UserError


class TaxInvoice(models.Model):
    _name = 'tax.invoice'
    _description = 'Tax Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char(string='Reference No', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: 'New')
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    source = fields.Char(string="Source", readonly=True)
    title = fields.Text(string="Title", required=False, store=True)
    date = fields.Date(string='Date', required=True)
    payment_term = fields.Many2one(comodel_name="account.payment.term", string='Payment Terms', required=False)
    sub_total = fields.Float(string='Sub total', compute='_compute_sub_cost', store=True)
    vat = fields.Float(string='VAT 18%', compute="vat_compute", store=True)
    amount_total = fields.Float(string='Grand Total', compute="compute_grand_total", store=True)
    amount_due = fields.Float(string='Amount Due', compute="_compute_total_amount_due", store=True)
    po = fields.Char(string="PO", required=False, store=True, readonly=True)
    total_amount_paid = fields.Float(string='Total Paid', compute="compute_total_amount_paid", store=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

    tax_invoice_line_ids = fields.One2many(comodel_name="tax.invoice.line",
                                           inverse_name="tax_invoice_id",
                                           string="Invoice Line Id",
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
        ('paid', 'Full Paid'),
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

    # @api.depends('name')
    # def _compute_total_amount_paid(self):
    #     for record in self:
    #         # Search for the account.move where invoice_origin matches the name in tax.invoice
    #         account_move = self.env['account.move'].search([('invoice_origin', '=', record.name)], limit=1)
    #
    #         # If a matching account.move is found, bring its amount_total (or amount_paid depending on your logic)
    #         if account_move:
    #             record.total_amount_paid = account_move.amount_total  # Or use 'amount_residual' if you want the remaining amount to be paid
    #         else:
    #             record.total_amount_paid = 0.0

    # @api.depends('name')
    # def _compute_total_amount_paid(self):
    #     for record in self:
    #         # Search for all account.move records where invoice_origin matches the name in tax.invoice
    #         account_moves = self.env['account.move'].search([('invoice_origin', '=', record.name)])
    #
    #         # Sum the amount_paid (or relevant field) from all matching account.move records
    #         total_paid = sum(
    #             move.amount_total for move in account_moves)  # Use 'amount_total' or 'amount_residual' as needed
    #
    #         # Update the total_amount_paid in tax.invoice
    #         record.total_amount_paid = total_paid

    # @api.depends('name', 'move_ids.amount_total', 'move_ids.amount_residual')
    def compute_total_amount_paid(self):
        for record in self:
            # Search for all account.move records where invoice_origin matches the name in tax.invoice
            account_moves = self.env['account.move'].search([('invoice_origin', '=', record.source)])

            # Sum the relevant amount (either amount_total, amount_residual, or another field)
            total_paid = sum(
                move.amount_total for move in account_moves)  # Amount paid = Total - Residual

            # Update the total_amount_paid in tax.invoice
            record.total_amount_paid = total_paid

    @api.depends('amount_total', 'total_amount_paid')
    def _compute_total_amount_due(self):
        for record in self:
            record.amount_due = record.amount_total - record.total_amount_paid
            if record.amount_due == 0 and record.amount_total == record.total_amount_paid:
                record.state = 'paid'
            elif 0 < record.amount_due < record.amount_total:
                record.state = 'partial'
            # elif record.amount_total == record.amount_due:
            #     record.state = 'confirmed'

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

        # for move in self:

        for record in self:
            confirmed_amount = self.env['confirmed.orders'].search([('name', '=', record.source)])
            # Check if the total amount exceeds the amount_due in tax.invoice
            if record.amount_total > confirmed_amount.amount_due:
                raise ValidationError(
                    "Total invoice amount can not be greater than amount due in confirmed sale order"
                )



        move_vals = {
            'move_type': 'out_invoice',  # Assuming it's a customer invoice (sale type)
            'partner_id': self.customer_id.id,
            'tax_invoice_ref': self.name,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': self.date,  # Due date as per your `date` field or a payment term
            'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,
            'invoice_origin': self.source,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.env['product.template'].search([
                        ('billboard_ref', '=', line.billboard_id.billboard_ref)
                    ], limit=1).id,
                    'name': line.billboard_id.name or 'Billboard service',
                    'quantity': line.no_of_months,
                    'price_unit': (line.rental_per_month * line.faces) + (line.material_cost + line.flighting_cost),
                    # 'quantity': float(line.no_of_months or 1),  # Quantity as float
                    # 'price_unit': float(line.rental_per_month or 0.0),  # Ensure price_unit is float
                    'tax_ids': [(6, 0, [
                        self.env['account.tax'].search([
                            ('amount', '=', 18),
                            ('type_tax_use', '=', 'sale')
                        ], limit=1).id
                    ])],
                    'account_id': self.env['account.account'].search([
                        ('user_type_id.type', '=', 'income')
                    ], limit=1).id,
                }) for line in self.tax_invoice_line_ids
            ]
        }

        # Create the account.move entry
        move = self.env['account.move'].create(move_vals)

        # Optional: Post the invoice automatically after creating it
        # if move:
        #     move.action_post()

        # Return an action to open the created invoice form view
        return {
            'name': 'Invoice',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': move.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def compute_amount_paid(self):
        for record in self:
            # Search for all account.move records where invoice_origin matches the name in tax.invoice
            account_moves = self.env['account.move'].search([('tax_invoice_ref', '=', record.name)])

            # Sum the relevant amount (either amount_total, amount_residual, or another field)
            total_paid = sum(move.amount_total for move in account_moves)

            # Update the total_amount_paid in tax.invoice
            record.total_amount_paid = total_paid

    # def action_confirm_invoice(self):
    #     self.state = 'confirmed'
    #
    #     # Prepare move (invoice) values
    #     move_vals = {
    #         'move_type': 'out_invoice',  # Customer invoice (sale type)
    #         'partner_id': self.customer_id.id,  # Customer on the tax invoice
    #         'invoice_date': fields.Date.context_today(self),  # Current date as invoice date
    #         'invoice_date_due': self.date,  # Due date from tax invoice
    #         'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,  # Sales journal
    #         'invoice_origin': self.name,  # Reference from the tax invoice
    #         'invoice_line_ids': []
    #     }
    #
    #     # Loop through each tax invoice line and create the corresponding account.move lines
    #     for line in self.tax_invoice_line_ids:
    #         # Get the product linked to the billboard (adjust the domain if needed)
    #         product = self.env['product.template'].search([
    #             ('billboard_ref', '=', line.billboard_id.billboard_ref)
    #         ], limit=1)
    #
    #         # Raise an error if no product is found to ensure correctness
    #         if not product:
    #             raise UserError('No product found for billboard %s' % line.billboard_id.name)
    #
    #         # Prepare invoice line values
    #         invoice_line_vals = {
    #             'product_id': product.id,  # Product linked to the billboard
    #             'name': line.billboard_id.name or 'Billboard service',  # Line description
    #             'quantity': float(line.no_of_months or 1),  # Quantity is number of months
    #             'price_unit': line.rental_per_month or 0.0,  # Price is rental per month
    #             'tax_ids': [(6, 0, [self.env['account.tax'].search([
    #                 ('amount', '=', 18),
    #                 ('type_tax_use', '=', 'sale')
    #             ], limit=1).id])],  # 18% VAT tax
    #             'account_id': self.env['account.account'].search([
    #                 ('user_type_id.type', '=', 'income')  # Income account
    #             ], limit=1).id,
    #         }
    #
    #         # Append the invoice line to the move
    #         move_vals['invoice_line_ids'].append((0, 0, invoice_line_vals))
    #
    #     # Create the account.move entry (invoice)
    #     move = self.env['account.move'].create(move_vals)
    #
    #     # Optional: Post the invoice automatically after creating it
    #     # if move:
    #     #     move.action_post()
    #
    #     return move

    # def action_confirm_invoice(self):
    #     self.state = 'confirmed'
    #
    #     move_vals = {
    #         'move_type': 'out_invoice',  # Assuming it's a customer invoice (sale type)
    #         'partner_id': self.customer_id.id,
    #         'invoice_date': fields.Date.context_today(self),
    #         'invoice_date_due': self.date,  # Due date as per your `date` field or a payment term
    #         'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,
    #         'invoice_origin': self.name,
    #         # Get default sales journal
    #         'invoice_line_ids': [(0, 0, {
    #             # 'product_id': 7,  # Assuming you have product in billboard
    #             'product_id': self.env['product.template'].search([
    #                 ('billboard_ref', '=', line.billboard_id.billboard_ref)
    #             ], limit=1).id,
    #             'name': line.billboard_id.name or 'Billboard service',
    #             'quantity': 1,
    #             # 'price_unit': self.sub_total,  # Assuming price from rental per month
    #             'price_unit': 3000,  # Assuming price from rental per month
    #             # 'tax_ids': 1,
    #             'tax_ids': [(6, 0, [
    #                 self.env['account.tax'].search([('amount', '=', 18), ('type_tax_use', '=', 'sale')], limit=1).id])],
    #             'account_id': self.env['account.account'].search([('user_type_id.type', '=', 'income')], limit=1).id,
    #         }) for line in self.tax_invoice_line_ids]  # Create an invoice line for each line in the tax invoice
    #     }
    #
    #     # Create the account.move entry
    #     move = self.env['account.move'].create(move_vals)
    #
    #     # Create contract for each billboard in the invoice lines
    #     # for line in self.tax_invoice_line_ids:
    #     #     contract_vals = {
    #     #         'name': self.env['ir.sequence'].next_by_code('contract.sequence') or 'New',
    #     #         'billboard_id': line.billboard_id.id,
    #     #         'customer_id': self.customer_id.id,
    #     #         'start_date': fields.Date.today(),  # Assuming the start date is today, can be customized
    #     #         'end_date': fields.Date.today() + relativedelta(months=line.no_of_months),
    #     #         # Calculating based on the number of months in the invoice line
    #     #     }
    #     #
    #     #     self.env['billboard.contract'].create(contract_vals)

    #     Acutomatic create invoice
    #     move_vals = {
    #         'move_type': 'out_invoice',  # Assuming it's a customer invoice (sale type)
    #         'partner_id': self.customer_id.id,
    #         'invoice_date': fields.Date.context_today(self),
    #         'invoice_date_due': self.date,  # Due date as per your `date` field or a payment term
    #         'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,
    #         'invoice_origin': self.name,
    #         # Get default sales journal
    #         'invoice_line_ids': [(0, 0, {
    #             # 'product_id': 7,  # Assuming you have product in billboard
    #             'product_id': self.env['product.template'].search([
    #                 ('billboard_ref', '=', line.billboard_id.billboard_ref)
    #             ], limit=1).id,
    #             'name': line.billboard_id.name or 'Billboard service',
    #             'quantity': line.no_of_months,
    #             # 'price_unit': self.sub_total,  # Assuming price from rental per month
    #             'price_unit': line.rental_per_month + 20,  # Assuming price from rental per month
    #             # 'tax_ids': 1,
    #             'tax_ids': [(6, 0, [
    #                 self.env['account.tax'].search([('amount', '=', 18), ('type_tax_use', '=', 'sale')], limit=1).id])],
    #             'account_id': self.env['account.account'].search([('user_type_id.type', '=', 'income')], limit=1).id,
    #         }) for line in self.tax_invoice_line_ids]  # Create an invoice line for each line in the tax invoice
    #     }

    # Create the account.move entry
    # move = self.env['account.move'].create(move_vals)

    # Optionally, post the invoice automatically
    # move.action_post()

    # @api.depends('name')
    # def action_create_invoice(self):
    #     # Create an account.move (invoice) record
    #     move_vals = {
    #         'move_type': 'out_invoice',  # Assuming it's a customer invoice (sale type)
    #         'partner_id': self.customer_id.id,
    #         'invoice_date': fields.Date.context_today(self),
    #         'invoice_date_due': self.date,  # Due date as per your `date` field or a payment term
    #         'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,
    #         'invoice_origin': self.name,
    #         # Get default sales journal
    #         'invoice_line_ids': [(0, 0, {
    #             # 'product_id': 7,  # Assuming you have product in billboard
    #             'product_id': self.env['product.template'].search([
    #                 ('billboard_ref', '=', line.billboard_id.billboard_ref)
    #             ], limit=1).id,
    #             'name': line.billboard_id.name or 'Billboard service',
    #             'quantity': 1,
    #             # 'price_unit': self.sub_total,  # Assuming price from rental per month
    #             'price_unit': 0,  # Assuming price from rental per month
    #             # 'tax_ids': 1,
    #             'tax_ids': [(6, 0, [
    #                 self.env['account.tax'].search([('amount', '=', 18), ('type_tax_use', '=', 'sale')], limit=1).id])],
    #             'account_id': self.env['account.account'].search([('user_type_id.type', '=', 'income')], limit=1).id,
    #         }) for line in self.tax_invoice_line_ids]  # Create an invoice line for each line in the tax invoice
    #     }
    #
    #     # Create the account.move entry
    #     move = self.env['account.move'].create(move_vals)
    #
    #     # Optionally, post the invoice automatically
    #     # move.action_post()
    #
    #     # return move  # Return the created move if needed
    #     # Return an action to open the created invoice form view
    #     return {
    #         'name': 'Invoice',
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_model': 'account.move',
    #         'res_id': move.id,
    #         'type': 'ir.actions.act_window',
    #         'target': 'current',
    #     }

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
    cost_subtotal = fields.Float(string='Total Cost', compute='_cost_subtotal_compute', store=True)

    tax_invoice_id = fields.Many2one(comodel_name="tax.invoice", string="Billboard ID",
                                     required=False)

    @api.depends("unit", "faces", "flighting_cost", "material_cost", "no_of_months", "rental_per_month")
    def _cost_subtotal_compute(self):
        for rec in self:
            rec.cost_subtotal = (rec.faces * rec.no_of_months * rec.rental_per_month) + (
                    rec.material_cost + rec.flighting_cost)
            # rec.cost_subtotal = rec.unit * rec.faces * \
            #                     (rec.material_cost if rec.material_cost != 0 else 1) * \
            #                     (rec.flighting_cost if rec.flighting_cost != 0 else 1) * \
            #                     (rec.no_of_months if rec.no_of_months != 0 else 1) * \
            #                     (rec.rental_per_month if rec.rental_per_month != 0 else 1)

            # rec.cost_subtotal = rec.unit * (rec.faces if rec.faces != 0 else 1) * rec.no_of_months * (
            #         rec.material_cost + rec.flighting_cost + rec.rental_per_month)


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    tax_invoice_ref = fields.Char(string='Tax Invoice Ref', store=True, readonly=True, )


#     amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_compute_amount')
#     amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_compute_amount')
#
#     @api.depends('invoice_line_ids.price_subtotal', 'invoice_line_ids.tax_ids', 'invoice_line_ids.price_total')
#     def _compute_amount(self):
#         for move in self:
#             untaxed_amount = 0.0
#             total_tax = 0.0
#             for line in move.invoice_line_ids:
#                 # Accumulate the subtotal of each line for the untaxed amount
#                 untaxed_amount += line.price_subtotal
#                 # Accumulate the tax for each line
#                 total_tax += sum(tax.amount for tax in line.tax_ids)
#
#             move.amount_untaxed = untaxed_amount
#             move.amount_tax = total_tax
#             # Calculate the total by adding untaxed amount and tax
#             move.amount_total = untaxed_amount + total_tax
#
#     @api.depends('amount_total')
#     def action_post(self):
#         # Call the original payment creation logic first
#         res = super(AccountMoveInherit, self).action_post()
#
#         for move in self:
#             tax_invoices = self.env['tax.invoice'].search([('name', '=', move.invoice_origin)])
#             # Check if the total amount exceeds the amount_due in tax.invoice
#             if move.amount_total > tax_invoices.amount_due:
#                 raise ValidationError(
#                     "Total invoice amount can not be greater than amount due in confirmed sale order"
#                     # f"The total invoice amount ({total_invoice_amount}) cannot exceed the amount due ({tax_invoice.amount_due}) in the related tax invoice."
#                 )
#
#             for record in tax_invoices:
#                 # Search for all account.move records where invoice_origin matches the name in tax.invoice
#                 account_moves = self.env['account.move'].search([('invoice_origin', '=', record.name)])
#
#                 # Sum the relevant amount (either amount_total, amount_residual, or another field)
#                 total_paid = sum(
#                     move.amount_total for move in account_moves)  # Amount paid = Total - Residual
#
#                 # Update the total_amount_paid in tax.invoice
#                 record.total_amount_paid = total_paid
#
#         return res
#
#     # @api.depends('invoice_line_ids.price_subtotal')
#     # def _compute_amount(self):
#     #     for move in self:
#     #         # Sum up price_subtotal for all lines
#     #         total_untaxed_amount = sum(line.price_subtotal for line in move.invoice_line_ids)
#     #         move.amount_untaxed = total_untaxed_amount
#     #         move.amount_tax = move.amount_untaxed * 0.18
#
#
class AccountMoveLineInherit(models.Model):
    _inherit = 'account.move.line'
    #
    #     # Define custom fields
    #     currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    #     no_faces = fields.Integer(string='Faces', default=1, store=True)
    #     cost_material = fields.Float(string='Material Cost', default=0.0, store=True)
    #     cost_flighting = fields.Float(string='Flighting Cost', default=0.0, store=True)
    quantity = fields.Integer(string='No of Month', default=1, store=True)
#     price_unit = fields.Float(string='Rental Price', default=1, store=True)
#     price_subtotal = fields.Float(
#         string='Subtotal',
#         readonly=True,
#         compute='_compute_price_subtotal',
#         store=True,
#         currency_field='currency_id'
#     )
#     untaxed_amount = fields.Float(
#         string='Untaxed Amount',
#         store=True,
#         readonly=True,
#         compute='_compute_untaxed_amount'
#     )
#
#     # @api.model
#     # def create(self, vals):
#     #     # Ensure custom fields are included when creating a new line
#     #     if 'no_faces' not in vals:
#     #         vals['no_faces'] = 1
#     #     if 'cost_material' not in vals:
#     #         vals['cost_material'] = 0.0
#     #     if 'flighting_cost' not in vals:
#     #         vals['flighting_cost'] = 0.0
#     #     return super(AccountMoveLineInherit, self).create(vals)
#     #
#     # def write(self, vals):
#     #     # Ensure custom fields are included when updating the line
#     #     if 'no_faces' not in vals:
#     #         vals['no_faces'] = self.no_faces
#     #     if 'cost_material' not in vals:
#     #         vals['cost_material'] = self.cost_material
#     #     if 'cost_flighting' not in vals:
#     #         vals['cost_flighting'] = self.cost_flighting
#     #     return super(AccountMoveLineInherit, self).write(vals)
#
#     @api.depends('no_faces', 'quantity', 'price_unit', 'cost_material', 'cost_flighting')
#     def _compute_price_subtotal(self):
#         for line in self:
#             # Subtotal calculation based on custom fields
#             line.price_subtotal = (line.no_faces * line.quantity * line.price_unit) + (
#                     line.cost_material + line.cost_flighting)
#
#     @api.depends('price_subtotal')
#     def _compute_untaxed_amount(self):
#         for line in self:
#             # Untaxed amount simply reflects the price subtotal
#             line.untaxed_amount = line.price_subtotal
