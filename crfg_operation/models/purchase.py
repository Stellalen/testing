import time
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import re    
import base64

class PersonContact(models.Model):
    _name = 'person.contact'
    _description = 'Person To Contact'
    
    name = fields.Char("Person To Contact")
    telephone = fields.Char("Telephone")
    
class EndUsers(models.Model):
    _name = 'end.users'
    _description = 'End Users'
    
    name = fields.Char("End User")
    
    

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    partner_contact_id = fields.Many2one("res.partner", "Contact")
    mrf_reference = fields.Char("MRF Reference")
    project_name = fields.Char("Name of Project")
    location_site = fields.Char("Location/Site")
    person_contact_id = fields.Many2one("person.contact","Person To Contact")
    telephone = fields.Char(related="person_contact_id.telephone", string="Telephone")
    end_user_id = fields.Many2one("end.users","End User")
    remarks = fields.Char("Remarks")
    multi_approval_id = fields.Many2one('multi.approval','Approval of Select/Award', copy=False)
    reception_date = fields.Datetime("Reception", compute='_compute_reception_date', store=True, copy=False,
        help="Completion date of the latest receipt order.")
    date_planned_realted = fields.Datetime(related="date_planned",
        string='Receipt (Date)', index=True, copy=False, help="related to Receipt Date (date_planned)")
    next_revision = fields.Integer("Next Revision", default=1, help="Used for multi Approval Revision", copy=False)
    
    @api.depends('picking_ids.date_done')
    def _compute_reception_date(self):
        for order in self:
            pickings = order.picking_ids.filtered(lambda x: x.state == 'done' and x.location_dest_id.usage == 'internal' and x.date_done)
            order.reception_date = max(pickings.mapped('date_done'), default=False)
    
    @api.onchange('picking_type_id')
    def onchange_shipping_type(self):
        if self.picking_type_id:
            partner = self.picking_type_id.warehouse_id.partner_id
            location_str = partner._display_address(without_company=True).replace('\n', ', ').replace('\r', '') .split(',')#.replace('\n', ', ').replace('\r', '')
            new_str = []
            for sub_str in location_str:
                if sub_str.strip():
                    new_str.append(sub_str.strip())
            location = str(self.picking_type_id.warehouse_id.name) +' - ' + str(', '.join(new_str))
            self.location_site = location
        
    def _prepare_invoice(self):
        self.ensure_one()
        vals = super(PurchaseOrder, self)._prepare_invoice()
        vals['do_date'] = self.effective_date
        return vals

    def action_rfq_send(self):
        action = super(PurchaseOrder, self).action_rfq_send()
        attachment_obj = self.env['ir.attachment']
        attachments =[]
        for picking in self.picking_ids.filtered(lambda p: p.state != 'cancel'):
            pdf_content, content_type = self.env.ref('stock.action_report_picking')._render_qweb_pdf(picking.id)
            filename = 'Picking Operation -'+ picking.name + '.pdf'
            attachments.append(attachment_obj.create({
                    'name': filename,
                    'type': 'binary',
                    'datas': base64.encodebytes(pdf_content),
                    'res_model': 'mail.compose.message',
                }).id)
        action.get('context',{}).update({'default_attachment_ids':[(6, 0, attachments)],
                                         'custom_layout':'mail.mail_notification_light'})
        return action
    
    def button_cancel(self):
        res = super(PurchaseOrder, self).button_cancel()
        for purchase in self:
            if self._context.get('menual_cancel',False):
                self.env['multi.approval.type'].update_x_field(
                    purchase, 'x_has_request_approval', False)
                self.env['multi.approval.type'].update_x_field(
                    purchase, 'x_review_result', False)
        return res
        
class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'
    
    def onchange_template_id(self, template_id, composition_mode, model, res_id):
        attachments = self.attachment_ids.ids
        result = super(MailComposer, self).onchange_template_id(template_id, composition_mode, model, res_id)
        if attachments and result.get('value',{}).get('attachment_ids',[]):
            existing_attachment = result.get('value').get('attachment_ids')[0][2]
            result.get('value').update({'attachment_ids':existing_attachment + attachments })
        return result
    
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    tbc = fields.Boolean("TBC", default=False)
    
    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()
        name = product_lang.name
        if product_lang.description:
            name += '\n' + product_lang.description
        return name
    
    @api.constrains('price_unit')
    def update_supplierinfo_constrains(self):
        for line in self.filtered(lambda l: not l.display_type):
                # Do not add a contact as a supplier
            partner = line.order_id.partner_id if not line.order_id.partner_id.parent_id else line.order_id.partner_id.parent_id
            # Convert the price in the right currency.
            currency = partner.property_purchase_currency_id or self.env.company.currency_id
            price = line.order_id.currency_id._convert(line.price_unit, currency, line.company_id, line.date_order or fields.Date.today(), round=False)
            # Compute the price for the template's UoM, because the supplier's UoM is related to that UoM.
            if line.product_id.product_tmpl_id.uom_po_id != line.product_uom:
                default_uom = line.product_id.product_tmpl_id.uom_po_id
                price = line.product_uom._compute_price(price, default_uom)
    
            supplierinfo = {
                'name': partner.id,
                'sequence': max(line.product_id.seller_ids.mapped('sequence')) + 1 if line.product_id.seller_ids else 1,
                'min_qty': 0.0,
                'price': price,
                'currency_id': currency.id,
                'delay': 0,
            }
            seller = line.product_id._select_seller(
                partner_id=line.partner_id,
                quantity=line.product_qty,
                date=line.order_id.date_order and line.order_id.date_order.date(),
                uom_id=line.product_uom)
            if seller:
                seller.write({'price':price})
            else:
                vals = {
                    'seller_ids': [(0, 0, supplierinfo)],
                }
                try:
                    line.product_id.write(vals)
                except AccessError:  # no write access rights -> just ignore
                    pass


