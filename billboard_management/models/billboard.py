
from odoo import models, fields, api, _


class Billboard(models.Model):
    _name = 'billboard.management'
    _description = 'Billboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char(string='Name', required=True)
    image_small = fields.Binary("Image", attachment=True)
    location = fields.Char(string='Location', required=True)
    size = fields.Char(string='Size', required=True)
    region = fields.Many2one(comodel_name='configuration.region', string='Region')
    media_type = fields.Many2one(comodel_name='configuration.media.type', string='Media Type')
    rental_price = fields.Float(string='Rental Price')
    billboard_ref = fields.Char(string='Billboard Reference', required=True, copy=False, readonly=True, index=True,
                                default=lambda self: 'New')
    availability = fields.Selection([
        ('available', 'Available'),
        ('rented', 'Rented'),
    ], string='Availability', default='available')

    total_booked_count = fields.Integer(
        string="Total Booked",
        compute="_compute_total_booked"
    )

    total_amount_cash = fields.Float(
        string="Total Amount Cash",
        compute="_compute_total_amount_cash"
    )

    @api.depends('billboard_ref')
    def _compute_total_booked(self):
        for record in self:
            record.total_booked_count = self.env['tax.invoice.line'].search_count([
                ('billboard_id', '=', record.id),
                # ('move_id.state', '=', 'posted')  # Assuming you only want posted invoices
            ])

    @api.depends('billboard_ref')
    def _compute_total_amount_cash(self):
        for record in self:
            total_amount = self.env['tax.invoice'].search([
                ('tax_invoice_line_ids.billboard_id', '=', record.id),
                # ('move_id.state', '=', 'posted')  # Only considering posted invoices
            ]).mapped('amount_total')  # Assuming price_total is the field in invoice lines
            record.total_amount_cash = sum(total_amount)
    #
    # def action_view_bookings(self):
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Bookings',
    #         'res_model': 'account.move.line',
    #         'view_mode': 'tree,form',
    #         'domain': [('billboard_ref', '=', self.billboard_ref)],
    #         'context': {'default_billboard_ref': self.billboard_ref},
    #     }

    def action_view_bookings(self):
        return {
            'name': _('Booking'),
            'domain': [('name', '=', self.id)],
            'view_type': 'form',
            'res_model': 'billboard.management',
            'view_id': False,
            'view_mode': 'tree,form',
            'type': 'ir.actions.act_window',
        }

    # def action_view_cash_amount(self):
    #     # Same structure as action_view_bookings, but showing amounts related to this billboard
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Cash Amount',
    #         'res_model': 'account.move.line',
    #         'view_mode': 'tree,form',
    #         'domain': [('billboard_ref', '=', self.billboard_ref)],
    #         'context': {'default_billboard_ref': self.billboard_ref},
    #     }

    @api.model
    def create(self, vals):
        # Generate a unique reference for the billboard if not provided
        if vals.get('billboard_ref', 'New') == 'New':
            vals['billboard_ref'] = self.env['ir.sequence'].next_by_code('billboard.management') or 'New'

        # Create the billboard record
        billboard = super(Billboard, self).create(vals)

        # Automatically create a corresponding product in product.template
        self.env['product.template'].create({
            'name': billboard.name,
            'list_price': billboard.rental_price,
            'type': 'service',  # Assuming the billboard is rented as a service
            'billboard_ref': billboard.billboard_ref,  # Custom field in product.template for the reference
        })

        return billboard


class ProductInherit(models.Model):
    _inherit = 'product.template'

    billboard_ref = fields.Char(string="Reference", required=False)
