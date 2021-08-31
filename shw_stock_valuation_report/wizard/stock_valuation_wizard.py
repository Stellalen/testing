import base64
from io import StringIO
from odoo import api, fields, models
from datetime import date
from odoo.tools.float_utils import float_round
from odoo.exceptions import Warning
from datetime import datetime, time as ttime 
import time
from collections import defaultdict
import io
from odoo.tools.float_utils import float_round, float_is_zero
try:
    import xlwt
except ImportError:
    xlwt = None

class StockValuationWizard(models.TransientModel):
    _name = "stock.valuation.wizard"
    
    start_date = fields.Date('Start Date', required=True, default=lambda *a: time.strftime('%Y-%m-01'))
    end_date = fields.Date('End Date', required=True, default=fields.Date.context_today)
    warehouse_ids = fields.Many2many('stock.warehouse', string='Warehouses')
    category_ids = fields.Many2many('product.category', string="Category")
    location_id = fields.Many2one('stock.location', string= 'Location')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    filter_by = fields.Selection([('product','Product'),('categ','Category')],string="Filter By",default = "categ")
    product_ids = fields.Many2many('product.product', string="Product")
    
    @api.onchange('warehouse_ids')
    def onchange_warehouse_ids(self):
        return {'domain': {'location_id':[('id','child_of',self.warehouse_ids.mapped('view_location_id.id'))]}}

    def print_report(self):
        report_xml_id = 'shw_stock_valuation_report.action_stock_valuation_report'
        return self.env.ref(report_xml_id).report_action(self)
#     
     
    def _get_category(self, data):
        category_obj = self.env['product.category']
        category_lst = []
        if data['filter_by'] == 'categ':
            domain = []
            if data['category_ids']:
                domain = [('id','child_of', data['category_ids'].ids)] 
            category_lst = category_obj.search(domain).ids
        return category_lst

    def _get_products(self, data, category_ids):
        product_obj = self.env['product.product']
        if data['filter_by'] == 'product':
            domain = []
            if data['product_ids']:
                products = data['product_ids']
            else:
                products = product_obj.search([('type', '=', 'product')])
        else:
            products = product_obj.search([('categ_id','in',category_ids),('type', '=', 'product')])
        return products

    def _get_outgoing_incoming_internal_qty(self, data, product, locations_lst):
        move_obj = self.env['stock.move']
        custom_domain = []
        if data['company_id']:
            custom_domain.append(('company_id','=',data['company_id'].id))
        if data['warehouse_ids'] :
            custom_domain.append(('picking_id.picking_type_id.warehouse_id','in',data['warehouse_ids'].mapped('id')))
        
        
        stock_moves = move_obj.search([
            ('product_id','=',product.id),
            ('picking_id.date_done','>',data['start_date']),
            ('picking_id.date_done',"<=",data['end_date']),
            ('state','=','done')
            ] + custom_domain)

        if locations_lst:
            outgoing_moves = stock_moves.filtered(lambda move: (move.picking_type_id.code == 'outgoing') 
                                                                and (move.location_id.id in locations_lst))
            incoming_moves = stock_moves.filtered(lambda move: (move.picking_type_id.code == 'incoming') 
                                                                and (move.location_dest_id.id in locations_lst))
            internal_moves = stock_moves.filtered(lambda move: (move.picking_type_id.code == 'internal') 
                                                                and ((move.location_id.id in locations_lst) 
                                                                     or (move.location_dest_id.id in locations_lst)
                                                                    ))
        else:
            outgoing_moves = stock_moves.filtered(lambda move: move.picking_type_id.code == 'outgoing')
            incoming_moves = stock_moves.filtered(lambda move: move.picking_type_id.code == 'incoming')
            internal_moves = stock_moves.filtered(lambda move: move.picking_type_id.code == 'internal')
            
        outgoing = sum(m.product_uom_qty for m in outgoing_moves) or 0.0
        incoming = sum(m.product_uom_qty for m in incoming_moves) or 0.0
        internal = sum(m.product_uom_qty for m in internal_moves) or 0.0
        return outgoing, incoming, internal
        
    def _get_adjust_quantity(self, data, product, locations_lst):
        move_obj = self.env['stock.move']
        inventory_domain = [('date','>',data['start_date']),
                            ('date',"<",data['end_date']),
                            ('product_id','=',product.id)]
        if not locations_lst and data['warehouse_ids']:
            locations_lst = self.env['stock.location'].search([('id','child_of',data['warehouse_ids'].mapped('lot_stock_id.id'))]).ids
        stock_plus_lines = move_obj.search([('location_id.usage', '=', 'inventory'),('location_dest_id','in',locations_lst)] + inventory_domain)
        stock_minus_lines = move_obj.search([('location_id.usage', '=', 'internal'),('location_dest_id.usage', '=', 'inventory'),('location_id','in',locations_lst)] + inventory_domain)
        
        plus_adjust = sum(m.product_uom_qty for m in stock_plus_lines) or 0.0
        minus_adjust = sum(m.product_uom_qty for m in stock_minus_lines) or 0.0
        adjust = plus_adjust - minus_adjust
        if adjust < 0.0:
            adjust = -int(adjust)
        return adjust
    
    def _get_costing_method_price(self, product, data):
        stock_val_layer = self.env['stock.valuation.layer'].search([
                ('product_id','=',product.id),
                ('create_date','>=',data['start_date']),
                ('create_date',"<=",data['end_date']),
                ] )

        layers = stock_val_layer.filtered(lambda layer:(not layer.stock_move_id.picking_id) and (layer.stock_move_id.picking_type_id.code == "incoming"))
        cost = sum (layer.value for layer in layers) or 0.00
        qty = sum (layer.quantity for layer in layers) or 0.00
        avg_cost = 0
        if qty > 0 :
            avg_cost = cost / qty
            avg_cost = round(avg_cost, 2)
        if avg_cost == 0:
            avg_cost = product.standard_price 
        method = ''
        price_used = product.standard_price 
        if product.categ_id.property_cost_method == 'average' :
            method = 'Average Cost (AVCO)'
            price_used = avg_cost 

        elif product.categ_id.property_cost_method == 'standard' :
            method = 'Standard Price'
            price_used = product.standard_price 
        return method, price_used
    
    def get_lines(self, data):
        product_obj = self.env['product.product']
        stock_move_obj = self.env['stock.move']
        
        datetime_start = datetime.combine(fields.Date.from_string(data['start_date']), ttime.min)
        datetime_end = datetime.combine(fields.Date.from_string(data['end_date']), ttime.max)
        data['start_date'] = datetime_start
        data['end_date'] = datetime_end
        
        locations_lst = []
        location = data['location_id'] and data['location_id'].id or False
        ctx = {}
        if data['warehouse_ids'] :
            ctx.update({'location':data['warehouse_ids'].mapped('view_location_id').ids})
        if data['location_id']:
            ctx.update({'location':data['location_id'].id})
            locations_lst = self.env['stock.location'].search([('id','child_of',data['location_id'].id)]).ids
            
        category_ids = self._get_category(data)
        lines = []
        for product in  self._get_products(data, category_ids) :
            opening_vals = product.with_context(ctx)._compute_quantities_dict(lot_id=False, owner_id=False, package_id=False, from_date=False, to_date=datetime_start)
            opening = opening_vals[product.id]['qty_available']
            
            sales_value, incoming, internal = self._get_outgoing_incoming_internal_qty(data, product, locations_lst)
            
            adjust = self._get_adjust_quantity(data, product, locations_lst)
                
            method, price_used = self._get_costing_method_price(product, data) 
            ending_bal = opening - sales_value + incoming + adjust
            confirm_ending_vals =  product.with_context(ctx)._compute_quantities_dict(lot_id=False, owner_id=False, package_id=False, from_date=False, to_date=data['end_date'])
            confirm_ending = confirm_ending_vals[product.id]['qty_available']
            
            vals = {
                    'categ_id':product.categ_id,
                    'sku': product.default_code or '',
                    'name': product.name or '',
                    'category': product.categ_id.name or '' ,
                    'cost_price': price_used,
                    'available':  0 ,
                    'virtual':   0,
                    'incoming': incoming,
                    'outgoing':  adjust,
                    'net_on_hand':   ending_bal,
                    'total_value': ending_bal * price_used,
                    'sale_value': sales_value,
                    'purchase_value':  0,
                    'beginning': opening,
                    'internal': internal,
                    'costing_method' : method,
                }
            lines.append(vals)

        return lines

    def get_lines_by_category(self, data):
        res = self.env['stock.valuation.wizard'].get_lines(data)
        rslt = defaultdict(lambda: [])
        for vals in res:
            rslt[vals['categ_id']].append(vals)
        return rslt

 
    def print_excel_report(self):
        if xlwt:
            data  = { 'start_date': self.start_date,
                     'end_date': self.end_date,
                     'warehouse_ids':self.warehouse_ids,
                     'category_ids':self.category_ids,
                     'location_id':self.location_id,
                     'company_id':self.company_id,
                    'currency':self.company_id.currency_id.name,
                    'product_ids': self.product_ids,
                    'filter_by' : self.filter_by
            }
            filename = 'Stock Valuation Report.xls'
            workbook = xlwt.Workbook()
            stylePC = xlwt.XFStyle()
            alignment = xlwt.Alignment()
            alignment.horz = xlwt.Alignment.HORZ_CENTER
            fontP = xlwt.Font()
            fontP.bold = True
            fontP.height = 200
            stylePC.font = fontP
            stylePC.num_format_str = '@'
            stylePC.alignment = alignment
            style_title = xlwt.easyxf(
            "font:height 300; font: name DejaVu Serif, bold on,color black; align: horiz center")
            style_table_header = xlwt.easyxf("font:height 200; font: name DejaVu Serif, bold on,color black; align: horiz center")
            style = xlwt.easyxf("font:height 200; font: name Liberation Sans,color black;")
            
            style_catg = xlwt.easyxf("font:height 250; font: name DejaVu Serif;")
            worksheet = workbook.add_sheet('Sheet 1')
            worksheet.write(5, 1, 'Start Date:', style_table_header)
            worksheet.write(6, 1, str(self.start_date))
            worksheet.write(5, 2, 'End Date', style_table_header)
            worksheet.write(6, 2, str(self.end_date))
            worksheet.write(5, 3, 'Company', style_table_header)
            worksheet.write(6, 3, self.company_id.name or '',)    
            worksheet.write(5, 4, 'Warehouse(s)', style_table_header)
            w_col_no = 7
            w_col_no1 = 8
            worksheet.write(6, 4,",".join(self.warehouse_ids.mapped('name')))
            worksheet.write_merge(0, 1, 2, 9, "Stock Valuation Report", style=style_title)
            worksheet.write(8, 0, 'Internal Reference', style_table_header)
            worksheet.write(8, 1, 'Name', style_table_header)
            worksheet.write(8, 2, 'Category', style_table_header)
            # worksheet.write(8, 3, 'Costing Method', style_table_header)
            worksheet.write(8, 3, 'Cost Price', style_table_header)
            worksheet.write(8, 4, 'Beginning', style_table_header)
            worksheet.write(8, 5, 'Internal', style_table_header)
            worksheet.write(8, 6, 'Received', style_table_header)
            worksheet.write(8, 7, 'Delivered', style_table_header)
            worksheet.write(8, 8, 'Adjustment', style_table_header)
            worksheet.write(8, 9, 'Ending', style_table_header)
            worksheet.write(8, 10, 'Valuation', style_table_header)
            prod_row = 9
            prod_col = 0
            
            if data['filter_by'] == 'product':
                for each in self.get_lines(data):
                    worksheet.write(prod_row, prod_col, each['sku'], style)
                    worksheet.write(prod_row, prod_col+1, each['name'], style)
                    worksheet.write(prod_row, prod_col+2, each['category'], style)
                    # worksheet.write(prod_row, prod_col+3, each['costing_method'], style)
                    worksheet.write(prod_row, prod_col+3, float_round(each['cost_price'],2), style)
                    worksheet.write(prod_row, prod_col+4, each['beginning'], style)
                    worksheet.write(prod_row, prod_col+5, each['internal'], style)
                    worksheet.write(prod_row, prod_col+6, each['incoming'], style)
                    worksheet.write(prod_row, prod_col+7, each['sale_value'], style)
                    worksheet.write(prod_row, prod_col+8, each['outgoing'], style)
                    worksheet.write(prod_row, prod_col+9, each['net_on_hand'], style)
                    worksheet.write(prod_row, prod_col+10, float_round(each['total_value'],2), style)
                    prod_row = prod_row + 1
                     
                prod_row = 8
                prod_col = 7
            else:
                get_line = self.get_lines_by_category(data)
                for categ in get_line:
                    worksheet.write_merge(prod_row, prod_row, prod_col, prod_col+7, "Category :"+ categ.display_name, style=style_catg)
                    prod_row +=1
                    prod_col = 0
                    for each in get_line[categ]:
                        worksheet.write(prod_row, prod_col, each['sku'], style)
                        worksheet.write(prod_row, prod_col+1, each['name'], style)
                        worksheet.write(prod_row, prod_col+2, each['category'], style)
                        # worksheet.write(prod_row, prod_col+3, each['costing_method'], style)
                        worksheet.write(prod_row, prod_col+3, float_round(each['cost_price'],2), style)
                        worksheet.write(prod_row, prod_col+4, each['beginning'], style)
                        worksheet.write(prod_row, prod_col+5, each['internal'], style)
                        worksheet.write(prod_row, prod_col+6, each['incoming'], style)
                        worksheet.write(prod_row, prod_col+7, each['sale_value'], style)
                        worksheet.write(prod_row, prod_col+8, each['outgoing'], style)
                        worksheet.write(prod_row, prod_col+9, each['net_on_hand'], style)
                        worksheet.write(prod_row, prod_col+10, float_round(each['total_value'],2), style)
                        prod_row = prod_row + 1
                prod_row +=1
                prod_col = 0
            fp = io.BytesIO()
            workbook.save(fp)
             
            export_id = self.env['excel.report.result.wizard'].create({'excel_file': base64.encodestring(fp.getvalue()), 'file_name': filename})
            res = {
                    'view_mode': 'form',
                    'res_id': export_id.id,
                    'res_model': 'excel.report.result.wizard',
                    'type': 'ir.actions.act_window',
                    'target':'new'
                }
            return res
        else:
            raise Warning (""" You Don't have xlwt library.\n Please install it by executing this command :  sudo pip3 install xlwt""")
         
 
 
