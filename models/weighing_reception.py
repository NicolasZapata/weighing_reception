# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError

_STATES = [
    ("in", "Entrada"),
    ("out", "Salida"),
    ("selection", "Selección"),
    ("received", "Recibido"),
]


class WeighingReception(models.Model):
    _name = "weighing.reception"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Weighing Reception"
    _order = "id desc"

    name = fields.Char(default="Nuevo", required=False)
    state = fields.Selection(_STATES, string="Estado", default="in")
    farmer_id = fields.Many2one(
        "res.partner", string="Agricultor", required=True, tracking=True
    )
    supplier_id = fields.Many2one("res.partner", string="Proveedor")
    vehicle_license_plate = fields.Char(string="Placa vehículo")
    driver_id = fields.Many2one("res.partner", string="Conductor")
    datetime_in = fields.Datetime(string="Fecha/hora recepción")
    datetime_out = fields.Datetime(string="Fecha/hora salida")
    employee_id = fields.Many2one("hr.employee", string="Receptor")
    transfer_ids = fields.Many2many("stock.picking", string="Entrada")
    transfer_count = fields.Integer(compute="_compute_transfer_count")
    uom_id = fields.Many2one("uom.uom", string="Unidad de medida")
    input_weight = fields.Float(string="Peso de entrada del vehículo")
    output_weight = fields.Float(string="Peso de salida del vehículo")
    product_weight = fields.Float(
        string="Peso del producto neto",
        compute="_compute_product_weight",
        tracking=True,
        readonly=True,
    )
    active = fields.Boolean(string="Activo", default=True)
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        domain="[('categ_id', '=', 'product_category_id')]",
        help="Producto (Se usa para filtrar los productos)",
    )
    product_category_id = fields.Many2one(
        "product.category",
        string="Categoría del Producto",
        help="Categoría del producto (Se usa para filtrar los productos por su categoría)",
    )
    product_name = fields.Char("Descripción")
    qty = fields.Float(string="Cantidad")
    product_uom_id = fields.Many2one("uom.uom", string="Medida")
    location_id = fields.Many2one(
        "stock.location",
        "Locación origen",
    )
    location_dest_id = fields.Many2one("stock.location", "Locación destino")
    no_countable_desc = fields.Float(string="Descontar el producto no contable")
    weight_basket = fields.Boolean(string="Descontar Canastillas")

    @api.model
    def create(self, vals):
        vals.update(
            name=self.env["ir.sequence"].next_by_code("weighting.reception") or _("New")
        )
        return super(WeighingReception, self).create(vals)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for record in self:
            if record.product_id:
                record.product_name = record.product_id.name
            else:
                record.product_name = False

    @api.depends("input_weight", "output_weight")
    def _compute_product_weight(self):
        for record in self:
            product_weight = 0.0
            if record.input_weight and record.output_weight:
                product_weight = record.input_weight - record.output_weight
            record.product_weight = product_weight

    @api.depends("transfer_ids")
    def _compute_transfer_count(self):
        for record in self:
            record.transfer_count = len(record.transfer_ids.ids)

    def action_view_transfer(self):
        self.ensure_one()
        action = {
            "name": _("Transferencias"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "context": {"create": False},
        }
        if len(self.transfer_ids) == 1:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": self.transfer_ids.id,
                }
            )
        else:
            action.update(
                {
                    "view_mode": "list,form",
                    "domain": [("id", "in", self.transfer_ids.ids)],
                }
            )
        return action

    def action_out(self):
        self.ensure_one()
        self.state = "out"

    def action_selection(self):
        self.ensure_one()
        self.state = "selection"

    def action_received(self):
        self.ensure_one()
        self.state = "received"

    def action_transfer(self):
        self.ensure_one()
        vals = {
            #'name': 'Incoming picking (negative product)',
            "partner_id": self.supplier_id.id,
            "picking_type_id": self.env.ref("stock.picking_type_in").id,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_dest_id.id,
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "name": self.product_name,
                        "product_id": self.product_id.id,
                        "product_uom": self.product_uom_id.id,
                        "product_uom_qty": self.qty,
                        "location_id": self.location_id.id,
                        "location_dest_id": self.location_dest_id.id,
                    },
                )
            ],
        }
        try:
            picking_id = self.env["stock.picking"].sudo().create(vals)
            self.transfer_ids += picking_id
        except Exception as e:
            raise ValidationError(_(e))

    def action_print(self):
        self.ensure_one()
        pass
