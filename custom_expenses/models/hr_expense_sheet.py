from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    check_number = fields.Char(string="Cheque Number", tracking=True)

    def write(self, vals):
        if 'check_number' in vals and not self.env.su:
            for sheet in self:
                if sheet.state == 'done' and (sheet.check_number or False) != (vals['check_number'] or False):
                    raise UserError(_(
                        "The Cheque Number of a paid expense report (%s) cannot be changed.",
                        sheet.name,
                    ))
        return super().write(vals)
