from odoo import _, api, fields, models

class ResPartner(models.Model):
  _inherit = "res.partner"

  is_farmer = fields.Boolean(string="Is Farmer")
  is_driver = fields.Boolean(string="Is Driver")