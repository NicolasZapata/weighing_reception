from odoo import fields, models

class PurchaseOrder(models.Model):
  _inherit = "purchase.order"

  weighing_reception_id = fields.Many2one("weighing.reception", string="Recepción")