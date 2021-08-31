# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseRequisition(models.Model):
    _inherit = "purchase.requisition"
    
    project_code = fields.Char("Project Code")
    requested_sign = fields.Image(string="Requested By")
    requested_name = fields.Char(string="Requested Name")
    requested_date = fields.Date(string="Requested Date")
    multi_approval_id = fields.Many2one('multi.approval','Approval of Select/Award', copy=False)
    next_revision = fields.Integer("Next Revision", default=1, help="Used for multi Approval Revision", copy=False)
    origin = fields.Char(string='Project Title')
    
    @api.model
    def create(self,vals):
        res = super(PurchaseRequisition, self).create(vals)
        # Set the sequence number regarding the requisition type
        if res.name == 'New':
            if res.is_quantity_copy != 'none':
                res.name = self.env['ir.sequence'].next_by_code('purchase.requisition.purchase.tender')
            else:
                res.name = self.env['ir.sequence'].next_by_code('purchase.requisition.blanket.order')
        return res


    def action_in_progress(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("You cannot confirm agreement '%s' because there is no product line.", self.name))
        if self.type_id.quantity_copy == 'none' and self.vendor_id:
            for requisition_line in self.line_ids:
                if requisition_line.price_unit <= 0.0:
                    raise UserError(_('You cannot confirm the blanket order without price.'))
                if requisition_line.product_qty <= 0.0:
                    raise UserError(_('You cannot confirm the blanket order without quantity.'))
                requisition_line.create_supplier_info()
            self.write({'state': 'ongoing'})
        else:
            self.write({'state': 'in_progress'})
            group = self.env.ref('crfg_operation.group_send_mail_on_confirm_requisition', raise_if_not_found=False)
            for user in group.users:
                template = self.env.ref('crfg_operation.email_template_on_confirm_purchase_requisition', raise_if_not_found=False)
                if template and self.id:
                    template.with_context(is_reminder=True, email_to_name=user.name).send_mail(
                        self.id,
                        force_send=True,
                        raise_exception=False,
                        email_values={'email_to': user.email, 'recipient_ids': []},
                        notif_layout="crfg_operation.mail_notification_light_with_link_for_PR")

    def action_draft(self):
        self.ensure_one()
        self.write({'state': 'draft'})

    def action_cancel(self):
        res = super(PurchaseRequisition, self).action_cancel()
        for requisition in self:
            if self._context.get('menual_cancel',False):
                self.env['multi.approval.type'].update_x_field(
                    requisition, 'x_has_request_approval', False)
                self.env['multi.approval.type'].update_x_field(
                    requisition, 'x_review_result', False)
        return res

class PurchaseRequisitionLine(models.Model):
    _inherit = "purchase.requisition.line"

    image_128 = fields.Image(related="product_id.image_128",string="Image", store=True)
    purpose = fields.Char("Purpose")
    deliver_to = fields.Many2one('stock.warehouse', string='Deliver To')
    contact_person = fields.Char("Contact Person")
    remarks = fields.Char('Remarks')
    

    @api.onchange('product_id')
    def _onchange_product_id(self):
        res = super(PurchaseRequisitionLine, self)._onchange_product_id()
        self.product_description_variants = self.product_id.description
        
        
    def write(self, vals):
        qty = self.product_qty
        res = super(PurchaseRequisitionLine, self).write(vals)
        if vals.get('product_qty',False) and self.requisition_id.multi_approval_id.line_ids.filtered(lambda apl: apl.state == 'Approved')\
                and self.requisition_id.multi_approval_id.state in ('Submitted','Approved') :
            self.env['mail.message'].create({
                'body': 'Quantity Changed :' + self.product_id.display_name +'<br/>'\
                        +' * '+ str(qty) + ' -> ' + str(vals.get('product_qty',0.0)),
                'model': 'purchase.requisition',
                'res_id': self.requisition_id.id,
                'subtype_id': '2',

                })
            if self.requisition_id.multi_approval_id.state in ('Approved',) and self.state in ('draft','cancel'):
                return res
            approval_line_ids = self.requisition_id.multi_approval_id.line_ids.filtered(lambda x:x.state == 'Approved')
            recipient_ids = approval_line_ids.mapped('user_id.partner_id.id')
            template = self.env.ref('crfg_operation.email_template_quantity_changed_purchase_requisition', raise_if_not_found=False)
            template.with_context(is_reminder=True, email_to_name=self.requisition_id.user_id.name, old_qty=qty).send_mail(
                    self.id,
                    force_send=True,
                    raise_exception=False,
                    email_values={'email_to': self.requisition_id.user_id.email, 'recipient_ids': recipient_ids},
                    notif_layout="crfg_operation.mail_notification_light_with_link_for_PR")
            
        return res
    
    def unlink(self):
        for rec in self:
            if rec.requisition_id.multi_approval_id:
                raise UserError(_('Can not DELETE after submit for Approval !.'))
        return super(PurchaseRequisitionLine, self).unlink()
        
