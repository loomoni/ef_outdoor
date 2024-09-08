from odoo import models, fields


class Region(models.Model):
    _name = 'configuration.region'
    _description = 'Region'

    name = fields.Char(string='Name', required=True)


class MediaType(models.Model):
    _name = 'configuration.media.type'
    _description = 'Media type'

    name = fields.Char(string='Name', required=True)
