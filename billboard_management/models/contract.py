from odoo import models, fields, api


class BillboardContract(models.Model):
    _name = 'billboard.contract'
    _description = 'Billboard Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char(string='Contract Reference', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: 'New')
    # billboard_id = fields.Many2one('billboard.management', string='Billboard', required=True)
    billboard_id = fields.Many2one(
        'billboard.management',
        string='Billboard',
        required=True,
        domain=[('availability', '=', 'available')]  # Domain to filter only available billboards
    )
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    source = fields.Char(string='Source', readonly=True, store=True)
    rental_price = fields.Float(string='Rental Price', related='billboard_id.rental_price')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('billboard.contract') or 'New'
        return super(BillboardContract, self).create(vals)

    def action_mark_active(self):
        self.state = 'active'

        # Mark the related billboard's availability as 'rented'
        if self.billboard_id:
            self.billboard_id.availability = 'rented'

    def action_cancel_contract(self):
        self.state = 'cancelled'

    @api.model
    def action_expire_contracts(self):
        today = fields.Date.today()
        expired_contracts = self.search([('end_date', '<=', today), ('state', '!=', 'expired')])
        for contract in expired_contracts:
            contract.button_expire()

    def button_expire(self):
        self.write({'state': 'expired'})
        if self.billboard_id:
            self.billboard_id.availability = 'available'
        return True
