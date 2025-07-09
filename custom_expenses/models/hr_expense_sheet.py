from odoo import models, fields

class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    check_number = fields.Char(string="Check Number")
