# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from odoo.addons.base.models.decimal_precision import dp
from odoo.exceptions import UserError, ValidationError
from io import BytesIO
import base64
from datetime import *
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell
from dateutil.relativedelta import relativedelta


# from odoo.addons import decimal_precision as dp


class PayrollSummaryWizard(models.TransientModel):
    _name = 'payroll.summary.wizard'
    _description = "Payroll Summary wizard table"

    date_from = fields.Date(string='Date From', required=True,
                            default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_to = fields.Date(string='Date To', required=True,
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    company = fields.Many2one('res.company', default=lambda self: self.env['res.company']._company_default_get(),
                              string="Company")

    def get_rules(self):
        vals = []

        heads = self.env['hr.salary.rule'].search([('active', 'in', (True))], order='sequence asc')
        list = []
        for head in heads:
            list = [head.name, head.code]
            vals.append(list)

        return vals

    def get_report(self):
        file_name = _('payroll summary ' + str(self.date_from) + ' - ' + str(self.date_to) + ' report.xlsx')
        fp = BytesIO()

        workbook = xlsxwriter.Workbook(fp)
        heading_format = workbook.add_format({'align': 'center',
                                              'valign': 'vcenter',
                                              'bold': True, 'size': 14})
        cell_text_format_n = workbook.add_format({'align': 'center',
                                                  'bold': True, 'size': 9,
                                                  })
        cell_text_format = workbook.add_format({'align': 'left',
                                                'bold': True, 'size': 9,
                                                })

        cell_text_format.set_border()
        cell_text_format_new = workbook.add_format({'align': 'left',
                                                    'size': 9,
                                                    })
        cell_text_format_new.set_border()
        cell_number_format = workbook.add_format({'align': 'right',
                                                  'bold': False, 'size': 9,
                                                  'num_format': '#,###0.00'})
        cell_number_format.set_border()
        worksheet = workbook.add_worksheet(
            'payroll summary ' + str(self.date_from) + ' - ' + str(self.date_to) + ' report.xlsx')
        normal_num_bold = workbook.add_format({'bold': True, 'num_format': '#,###0.00', 'size': 9, })
        normal_num_bold.set_border()
        worksheet.set_column('A:A', 20)
        worksheet.set_column('B:B', 20)
        worksheet.set_column('C:C', 20)
        worksheet.set_column('D:D', 20)
        worksheet.set_column('E:E', 20)
        worksheet.set_column('F:F', 20)
        worksheet.set_column('G:G', 20)
        worksheet.set_column('H:H', 20)
        worksheet.set_column('I:I', 20)
        worksheet.set_column('J:J', 20)
        worksheet.set_column('K:K', 20)
        worksheet.set_column('L:L', 20)
        worksheet.set_column('M:M', 20)
        worksheet.set_column('N:N', 20)

        res = self.get_rules()
        row = 2
        row_set = row

        if self.date_from and self.date_to:

            date_2 = datetime.strftime(self.date_to, '%d-%m-%Y')
            date_1 = datetime.strftime(self.date_from, '%d-%m-%Y')
            payroll_month = self.date_from.strftime("%B")
            worksheet.merge_range('A1:F2', 'Payroll For %s %s' % (payroll_month, self.date_from.year),
                                  heading_format)
            worksheet.merge_range('B4:D4', '%s' % (self.company.name), cell_text_format_n)
            column = 0
            worksheet.write(row + 1, 0, 'Company', cell_text_format_n)
            worksheet.write(row, 4, 'Date From', cell_text_format_n)
            worksheet.write(row, 5, date_1 or '')
            row += 1
            worksheet.write(row, 4, 'Date To', cell_text_format_n)
            worksheet.write(row, 5, date_2 or '')
            row += 2

            worksheet.write(row, 0, 'NAME OF EMPLOYEE', cell_text_format)
            worksheet.write(row, 1, 'ACCOUNT NO.', cell_text_format)

            column = 2
            # to write salary rules names in the row
            for vals in res:
                worksheet.write(row, column, vals[0], cell_text_format)
                column += 1
            row += 1
            col = 0
            ro = row

            # payslipResult = self.sudo().compute_employee_payslips(self.date_from,self.date_to)

            payslip_ids = self.env['hr.payslip'].sudo().search(
                [('date_from', '>=', self.date_from), ('date_to', '<=', self.date_to), ('state', '=', 'done')])
            if payslip_ids:

                for payslip in payslip_ids:
                    name = payslip.employee_id.name
                    id = payslip.employee_id.bank_account_id.acc_number

                    worksheet.write(ro, col, name or '', cell_text_format_new)
                    worksheet.write(ro, col + 1, id or '', cell_text_format_new)

                    ro = ro + 1
            col = col + 2
            colm = col

            if payslip_ids:
                for payslip in payslip_ids:
                    for vals in res:
                        r = 0
                        check = False
                        for line in payslip.line_ids:
                            if line.code == vals[1]:
                                check = True
                                r = line.total

                        if check == True:

                            worksheet.write(row, col, r, cell_number_format)


                        else:
                            worksheet.write(row, col, 0, cell_number_format)

                        col += 1
                    row += 1
                    col = colm
        worksheet.write(row, 0, 'Grand Total', cell_text_format)
        # calculating sum of columnn
        roww = row
        columnn = 2
        for vals in res:
            cell1 = xl_rowcol_to_cell(row_set + 1, columnn)

            cell2 = xl_rowcol_to_cell(row - 1, columnn)
            worksheet.write_formula(row, columnn, '{=SUM(%s:%s)}' % (cell1, cell2), normal_num_bold)
            columnn = columnn + 1

        worksheet.write(row, 1, '', cell_text_format)
        worksheet.write(row, 2, '', cell_text_format)

        workbook.close()
        file_download = base64.b64encode(fp.getvalue())
        fp.close()

        self = self.with_context(default_name=file_name, default_file_download=file_download)

        return {
            'name': 'Payroll Summary Report Download',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'payroll.summary.excel',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': self._context,
        }


class PayrollReportExcel(models.TransientModel):
    _name = 'payroll.summary.excel'

    name = fields.Char('File Name', size=256, readonly=True)
    file_download = fields.Binary('Download Payroll', readonly=True)


class InheritPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    receipt_no = fields.Char(string='Receipt No.')


class HrExpenseInherit(models.Model):
    _inherit = 'hr.expense'

    supplier_information = fields.Many2one(comodel_name='res.partner', string='Supplier')


class HrPayslipInherit(models.Model):
    _inherit = 'hr.payslip'

    struct_id = fields.Many2one('hr.payroll.structure', string="Structure", readonly=False)

    # def action_payslip_done(self):
    #     checkPayslip = False
    #     for payslip in self.slip_ids:
    #         if self.env['hr.payslip'].search(
    #                 [('employee_id', '=', payslip.employee_id.id), ('state', '=', 'done'),
    #                  ('date_to', '>', payslip.date_from)]):
    #             checkPayslip = True
    #             break
    #     if not checkPayslip:
    #         for payslip in self.slip_ids:
    #             if payslip.state != 'cancel':
    #                 payslip.action_payslip_done()
    #         self.write({'state': 'done'})
    #     else:
    #         raise ValidationError(_('The already exists a payslip for the specified period for selected employees.'))
    #
    #     return True

    def return_draft(self):
        self.write({'state': 'draft'})
        return True
