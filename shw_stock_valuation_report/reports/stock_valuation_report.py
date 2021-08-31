from odoo import models, fields, api
from datetime import date
from odoo.tools.float_utils import float_round
from datetime import datetime, time
from collections import defaultdict


class StaockValuationReport(models.AbstractModel):
    _name = 'report.shw_stock_valuation_report.stock_val_report_tmpl'
    
    def _get_report_values(self, docids, data=None):
        data = data if data is not None else {}
        docs = self.env['stock.valuation.wizard'].browse(docids)
        data  = {'product_ids':docs.product_ids , 
                 'filter_by':docs.filter_by,
                 'start_date': docs.start_date, 
                 'end_date': docs.end_date,
                 'warehouse_ids':docs.warehouse_ids,
                 'category_ids':docs.category_ids,
                 'location_id':docs.location_id,
                 'company_id':docs.company_id,
                 'currency':docs.company_id.currency_id.name}
        return {
                   'doc_model': 'stock.valuation.wizard',
                   'data' : data,
                    'get_warehouse' : self._get_warehouse_name,
                   'get_lines':self._get_lines,
                    'get_lines_by_category' : self._get_lines_by_category,
                   }

    def _get_warehouse_name(self,warehouse_ids):
        return ",".join(warehouse_ids.mapped('name'))

    def _get_lines(self, data):
        return self.env['stock.valuation.wizard'].get_lines(data)

    def _get_lines_by_category(self, data):
        return self.env['stock.valuation.wizard'].get_lines_by_category(data)
        
            
