from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, Warning


class RequestApproval(models.TransientModel):
    _inherit = 'request.approval'

    @api.model
    def default_get(self, fs):
        res = super(RequestApproval, self).default_get(fs)
        ctx = self._context
        model_name = ctx.get('active_model')
        res_id = ctx.get('active_id')
        if res_id and model_name == 'purchase.requisition':
            record = self.env[model_name].browse(res_id)
            if any ((ln.product_qty <= 0.0) or (not ln.product_uom_id) \
                    or (not ln.schedule_date) or (not ln.purpose) \
                    or (not ln.deliver_to) or (not ln.contact_person) for ln in record.line_ids):
                raise Warning(
                _('Quantity, UoM, Date REQ, Purpose, Deliver To, Contact Person Details are required for each Requisition line !'))
            if (not record.requested_sign) \
                    or (not record.requested_name) \
                    or (not record.requested_date):
                raise Warning(
                _('Requested Signature, Name & Date are Required !'))
        if res_id and model_name in ('purchase.requisition', 'purchase.order'):
            # Revision no. logic
            record = self.env[model_name].browse(res_id)
            if record.multi_approval_id:
                res.update({ 'name': res.get('name')+'-R'+str(record.next_revision)})
        return res
    
    def action_request(self):
        res = super(RequestApproval, self).action_request()
        approval_id = res.get('res_id',False)
        if self.origin_ref._name in ('purchase.requisition', 'purchase.order'):
            self.origin_ref.multi_approval_id = res.get('res_id',False)
            self.origin_ref.next_revision += 1
#         approval = self.env['multi.approval'].browse(approval_id)    
#         template = self.env.ref('crfg_operation.email_template_todo_validate_approval', raise_if_not_found=False)
#         template.with_context(is_reminder=True, email_to_name=approval.pic_id.name).send_mail(
#                     approval_id,
#                     force_send=True,
#                     raise_exception=False,
#                     email_values={'email_to': approval.pic_id.email, 'recipient_ids': []},
#                     notif_layout="crfg_operation.mail_notification_light_with_link")
        return res
    
    

class MultiApproval(models.Model):
    _inherit = 'multi.approval'
    
    def action_submit(self):
        res = super(MultiApproval, self).action_submit()
        approval = self    
        template = self.env.ref('crfg_operation.email_template_todo_validate_approval', raise_if_not_found=False)
        template.with_context(is_reminder=True, email_to_name=approval.pic_id.name).send_mail(
                    approval.id,
                    force_send=True,
                    raise_exception=False,
                    email_values={'email_to': approval.pic_id.email, 'recipient_ids': []},
                    notif_layout="crfg_operation.mail_notification_light_with_link")    
        return res    
        
    def set_approved(self):
        res = super(MultiApproval, self).set_approved()
        if not self.origin_ref:
            self.type_id.approval_email_notification(self, action="approve")
        return res
    
    def send_todo_validate_email_notification(self):
        template = self.env.ref('crfg_operation.email_template_todo_validate_approval', raise_if_not_found=False)
        template.with_context(is_reminder=True, email_to_name=self.pic_id.name).send_mail(
                    self.id,
                    force_send=True,
                    raise_exception=False,
                    email_values={'email_to': self.pic_id.email, 'recipient_ids': []},
                    notif_layout="crfg_operation.mail_notification_light_with_link")
        return True

        
        
    def action_refuse(self, reason=''):
        res = super(MultiApproval, self).action_refuse(reason=reason)
        recipient_ids = []
        record = self.origin_ref and self.origin_ref or self
        recipient_ids.append(record.user_id.partner_id.id)
        approval_line_ids = self.line_ids.filtered(lambda x:x.state == 'Approved')
        recipient_ids.extend(approval_line_ids.mapped('user_id.partner_id.id'))
        template = self.env.ref('crfg_operation.email_template_refuse_approval', raise_if_not_found=False)
        
        template.with_context(is_reminder=True, email_to_name=self.pic_id.name, reason=reason).send_mail(
                    self.id,
                    force_send=True,
                    raise_exception=False,
                    email_values={'recipient_ids': recipient_ids},
                    notif_layout="crfg_operation.mail_notification_light_with_link")
        return res
        
       
    @api.constrains('name')
    def check_approval_title(self):
        approval_ids = self.search([('id','!=',self.id),('name','=',self.name)])
        if approval_ids:
            raise Warning(
                _('Requested Title for Approval Is Duplicated, Please give Unique Title!'))
        
class MultiApprovalType(models.Model):
    _inherit = 'multi.approval.type'

    @api.model
    def open_request(self):
        ctx = self._context
        model_name = ctx.get('active_model')
        res_id = ctx.get('active_id')
        origin_ref = '{model},{res_id}'.format(
            model=model_name, res_id=res_id)
            
        result = {
            'name': 'My Requests',
            'type': 'ir.actions.act_window',
            'res_model': 'multi.approval',
            'view_type': 'list',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('origin_ref', '=', origin_ref)],
        }
        request_ids = self.env['multi.approval'].search([('origin_ref', '=', origin_ref)])
        if len(request_ids) ==1:
            res = self.env.ref('multi_level_approval.multi_approval_view_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = request_ids.id
        return result

    def _run(self, record, action):
        self.ensure_one() 
        res = False
        func_name = 'get_action_%s_code' % action
        if hasattr(self, func_name):
            func = getattr(self, func_name)
            python_code = func(action)
            if not python_code:
                return res
            eval_context = self._get_eval_context(record)
            res = self.exec_func(python_code, eval_context)
            self.approval_email_notification(record, action)
        return res

    def approval_email_notification(self, record, action):
         
        if action != "approve":
            return True
        if not 'multi_approval_id' in record._fields:
            multi_approval_id = record.id
        else: multi_approval_id = record.multi_approval_id.id
            
        
        template2 = self.env.ref('crfg_operation.email_template_for_approved_purchase_requisition', raise_if_not_found=False)
        if template2 and record:
            template2.with_context(is_reminder=True, email_to_name=record.user_id.name).send_mail(
                multi_approval_id,
                force_send=True,
                raise_exception=False,
                email_values={'email_to': record.user_id.email, 'recipient_ids': []},
                notif_layout="crfg_operation.mail_notification_light_with_link")
        return True

class MultiApprovalLine(models.Model):
    _inherit = 'multi.approval.line'

    approval_sign = fields.Binary(string="Signature", copy=False)
    date_approve = fields.Date("Approved Date")

    def set_approved(self):
        res = super(MultiApprovalLine, self).set_approved()
        if not self.approval_sign:
            raise Warning(
                _('Approver Signature must be Required !'))
        self.date_approve = fields.date.today()
        if self.approval_id.line_id.state == 'Waiting for Approval':
            self.approval_id.send_todo_validate_email_notification()
        return res
        