from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class UomUom(models.Model):
    _inherit = "uom.uom"

    printed_uom = fields.Char("Printed UoM")

class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _type_selection_lst(self):
        return [('service', 'Service/Rental/Calibration'), ('product', 'Storable Product')]

    type = fields.Selection(selection=_type_selection_lst, string='Product Type', default='service', required=True,)
    
    
    @api.onchange('type')
    def _onchange_type(self):
        res = super(ProductTemplate, self)._onchange_type()
        if self.type == 'service':
            self.invoice_policy = 'order'
            self.purchase_method = 'purchase'
        else:
            self.invoice_policy = 'delivery'
            self.purchase_method = 'receive'
        return res
