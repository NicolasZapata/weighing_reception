from odoo import _, api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.template"

    available_in_stock = fields.Boolean(
        "Disponible en pesaje de compras", default=False
    )
