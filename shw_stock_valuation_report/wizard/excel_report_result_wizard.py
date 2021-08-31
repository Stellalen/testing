from odoo import api, fields, models, _


class ExcelReportResultWizard(models.TransientModel):
    _name = "excel.report.result.wizard"
     
     
    excel_file = fields.Binary('Daily Sales Report ')
    file_name = fields.Char('Excel File', size=64)
