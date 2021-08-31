from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    do_number = fields.Char("DO Number")
    do_date = fields.Date("Delivery Date")
    related_bank_id = fields.Many2one('res.bank', related="partner_bank_id.bank_id", string="Recipient Bank")
    
