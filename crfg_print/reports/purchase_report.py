import re

from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from odoo.osv.expression import expression


class PurchaseReport(models.Model):
    _inherit = "purchase.report"

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if self.user_has_groups('crfg_operation.group_purchase_own_documents'):
            domain.extend(['|',('user_id','=',self._uid),('user_id','=',False)])
        res = super(PurchaseReport, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        return res
        
        