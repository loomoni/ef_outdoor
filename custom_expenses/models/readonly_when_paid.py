import json

from lxml import etree

from odoo import api, models

# Fields that must stay usable on a paid record (chatter, status bar, ...).
_ALWAYS_EDITABLE = {
    'state', 'message_follower_ids', 'message_ids', 'activity_ids',
    'message_attachment_count', 'attachment_number',
}
_PAID = ['state', '=', 'done']


def _lock_form_when_paid(arch):
    """Return `arch` with every editable top-level field of the form made
    read-only when the record's state is 'done' (Paid)."""
    doc = etree.fromstring(arch)
    for node in doc.iter('field'):
        if node.get('name') in _ALWAYS_EDITABLE:
            continue
        # Skip fields of embedded one2many sub-views: making the parent x2many
        # field read-only already locks its lines.
        if any(a.tag == 'field' for a in node.iterancestors()):
            continue
        if any('oe_chatter' in (a.get('class') or '') for a in node.iterancestors()):
            continue
        modifiers = json.loads(node.get('modifiers') or '{}')
        readonly = modifiers.get('readonly', False)
        if readonly is True:
            continue
        if isinstance(readonly, list) and readonly:
            modifiers['readonly'] = ['|', _PAID] + readonly
        else:
            modifiers['readonly'] = [_PAID]
        node.set('modifiers', json.dumps(modifiers))
    return etree.tostring(doc, encoding='unicode')


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form' and 'state' in res.get('fields', {}):
            res['arch'] = _lock_form_when_paid(res['arch'])
        return res


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form' and 'state' in res.get('fields', {}):
            res['arch'] = _lock_form_when_paid(res['arch'])
        return res
