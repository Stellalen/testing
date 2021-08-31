import time
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

#     sign_initials = fields.Binary(string="Authorised Signature")
    sign_signature = fields.Image(string="Recipient's Signature", copy=False)
    is_internal_delivery = fields.Boolean("Internal Delivery", default=False)
    is_external_delivery = fields.Boolean("External Delivery", default=False)
    vehicle_no = fields.Char("Vehicle No.")
    name_detail = fields.Char("Name Detail")
    nric_fin_no = fields.Char("NRIC/FIN No.")
    sign_signature_name = fields.Char("Recipient's Name", copy=False)
    sign_date_time = fields.Datetime("Date & Time", copy=False)
    do_note = fields.Text("Note for Delivery Order") 
    supplier_do_number = fields.Char("Supplier DO Number")
    
    def button_validate(self):
        if (self.picking_type_code in ('outgoing','internal')) \
            and (not self.sign_signature or not self.signature \
                 or not self.sign_signature_name or not self.sign_date_time):
            raise UserError(_("Signatures (With Name & Datetime) are mandatory to validate the DO."))
        elif (self.picking_type_code == 'incoming') \
            and (not self.sign_signature  \
                 or not self.sign_signature_name or not self.sign_date_time):
            raise UserError(_("Signature (With Name & Datetime) are mandatory to validate the Receipt."))
        return  super(StockPicking, self).button_validate()
    
    
class StockMove(models.Model):
    _inherit = 'stock.move'
    
    date = fields.Datetime(string="Date Processing")
    date_deadline = fields.Datetime(string="Scheduled Date")
    sign_date_time = fields.Datetime(related="picking_id.sign_date_time", string="Sign Date & Time")
    

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super(StockMove, self)._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant)
        if self.picking_id.picking_type_code == 'incoming':
            lot_obj = self.env['stock.production.lot']
            lot = lot_obj.search([('name','=',self.picking_id.name),
                          ('product_id','=',self.product_id.id),
                          ('company_id','=',self.company_id.id)], limit=1)
            if not lot:
                lot = lot_obj.create({'name':self.picking_id.name,
                                    'product_id':self.product_id.id,
                                    'company_id':self.company_id.id,
                                    'currency_id':self.purchase_line_id.currency_id and self.purchase_line_id.currency_id.id or False,
                                    'purchase_unit_price': self.purchase_line_id.price_unit,
                                    'unit_value':self.stock_valuation_layer_ids and self.stock_valuation_layer_ids[0].unit_cost,
                                    'partner_id':self.purchase_line_id.order_id.partner_id.id,
                                    
                                    })
            vals.update({'lot_id':lot.id, }) #'lot_name':lot.name
        return vals
    
    
    def _create_in_svl(self, forced_quantity=None):
        """Create a `stock.valuation.layer` from `self`.

        :param forced_quantity: under some circunstances, the quantity to value is different than
            the initial demand of the move (Default value = None)
        """
        svl_ids = super(StockMove, self)._create_in_svl(forced_quantity = forced_quantity)
        for svl in svl_ids:
            svl.stock_move_id._get_in_move_lines().mapped('lot_id').write({'unit_value':svl.unit_cost})
        return svl_ids
        
 
class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'
    
    currency_id = fields.Many2one("res.currency", "Currency")
    company_currency_id = fields.Many2one(related="company_id.currency_id", string="Company Currency", store=True)
    purchase_unit_price = fields.Monetary(string='Unit Price') 
    unit_value = fields.Monetary(string='Unit Value', help="Stock Valuation Layer/Unit Value") 
    partner_id = fields.Many2one("res.partner", string="Partner", help="Purchase Order Line/Partner")
    
    
    

    