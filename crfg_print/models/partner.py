from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    def _display_address(self, without_company=False):
        ctx = dict(self._context or {})
        if ctx.get('without_company',False):
            without_company = True
        return super(ResPartner, self)._display_address(without_company=without_company)

    
