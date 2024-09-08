from odoo import models, fields


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
    availability = fields.Selection([
        ('available', 'Available'),
        ('rented', 'Rented'),
    ], string='Availability', default='available')


class ProductInherit(models.Model):
    _inherit = 'product.template'
