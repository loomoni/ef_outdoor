from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    expense_check_number = fields.Char(
        string="Cheque Number",
        compute='_compute_expense_check_number',
        search='_search_expense_check_number',
        help="Cheque Number of the expense report this entry belongs to or pays.",
    )

    @api.model
    def _expense_sheets_of_moves(self, moves):
        """Expense reports linked to `moves`: either the report's own journal
        entry, or a payment entry reconciled with it."""
        lines = moves.line_ids
        counterpart_moves = (
            lines.matched_debit_ids.debit_move_id.move_id
            | lines.matched_credit_ids.credit_move_id.move_id
        )
        all_moves = moves | counterpart_moves
        return self.env['hr.expense.sheet'].sudo().search(
            [('account_move_id', 'in', all_moves.ids)])

    def _compute_expense_check_number(self):
        cache = {}
        for line in self:
            move = line.move_id
            if move.id not in cache:
                sheets = self._expense_sheets_of_moves(move) if move else []
                numbers = [s.check_number for s in sheets if s.check_number]
                cache[move.id] = ', '.join(dict.fromkeys(numbers)) or False
            line.expense_check_number = cache[move.id]

    def _search_expense_check_number(self, operator, value):
        sheet_domain = [('check_number', operator, value)]
        if operator in ('=', '!=') and not value:
            # "is set" / "is not set": search the opposite set and negate.
            positive = operator == '!='
            sheet_domain = [('check_number', '!=', False)]
        else:
            positive = operator not in ('!=', 'not ilike', 'not like', 'not in')
            if not positive:
                neg = {'!=': '=', 'not ilike': 'ilike', 'not like': 'like', 'not in': 'in'}
                sheet_domain = [('check_number', neg[operator], value)]
        sheets = self.env['hr.expense.sheet'].sudo().search(sheet_domain)
        moves = sheets.account_move_id
        lines = moves.line_ids
        moves |= (
            lines.matched_debit_ids.debit_move_id.move_id
            | lines.matched_credit_ids.credit_move_id.move_id
        )
        return [('move_id', 'in' if positive else 'not in', moves.ids)]
