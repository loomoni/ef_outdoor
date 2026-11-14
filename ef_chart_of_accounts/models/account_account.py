from odoo import _, fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    transaction_line_ids = fields.One2many(
        'account.move.line', 'account_id',
        string="Transaction Items",
        domain=[('parent_state', '=', 'posted')],
        readonly=True,
    )

    def action_open_transaction_items(self):
        """Balance button: posted journal items of this account, with the
        expense Cheque Number column."""
        self.ensure_one()
        return {
            'name': _("Journal Items: %s", self.display_name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref('account.view_move_line_tree').id, 'tree'),
                (False, 'form'),
            ],
            'domain': [('account_id', '=', self.id)],
            'context': {'search_default_posted': 1, 'create': False},
        }
