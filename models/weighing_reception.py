# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError

# State definitions list
_STATES = [
    ("draft", "New"),
    ("in", "Input"),
    ("out", "Exit"),
    ("selection", "Selectión"),
    ("received", "Received"),
]


class WeighingReception(models.Model):
    _name = "weighing.reception"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Weighing Reception"
    _order = "id desc"

    name = fields.Char(default="New", required=False)
    state = fields.Selection(_STATES, string="State", default="draft")
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
    vehicle_uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad de medida del vehículo",
        store=True,
    )
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
        help="Producto (Se usa para filtrar los productos)",
    )
    categ_id = fields.Many2one(
        "product.category",
        string="Categoría del Producto",
        help="Categoría del producto (Se usa para filtrar los productos por su categoría)",
    )
    product_name = fields.Char("Descripción")
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Medida del producto",
        related="product_id.uom_id",
        store=True,
    )
    # basket | canastillas -----------------------------------------------------------------------------
    qty_basket = fields.Float(string="Cantidad de canastillas")
    basket_uom_name = fields.Char(
        string="Medida de Canastilla",
        related="basket_product_id.weight_uom_name",
    )
    basket_product_weight_unit = fields.Float(
        string="Peso de canastillas", related="basket_product_id.weight"
    )
    basket_product_weight = fields.Float(
        string="Peso de canastillas"
    )

    weight_basket = fields.Boolean(string="Descontar Canastillas")
    basket_product_id = fields.Many2one(
        "product.product", string="Producto de Canastilla"
    )
    # ---------------------------------------------------------------------------------------------
    # Not countable | Producto No Conforme -------------------------------------------------------
    discount_product = fields.Boolean(string="Aplicar descuento del producto")
    not_countable_weight = fields.Float(string="Peso de producto no conforme")
    not_countable_weight_uom_name = fields.Char(
        string="Medida de producto no conforme",
        related="product_id.weight_uom_name"
    )
    no_countable_desc = fields.Float(string="Producto no conforme")
    # ------------------------------------------------------------------------------------------------
    location_id = fields.Many2one(
        "stock.location",
        "Locación origen",
    )
    order_ids = fields.One2many(
        "purchase.order",
        "weighing_reception_id",
        string="Ordenes de compra",
    )
    purchase_order_counts = fields.Integer(
        compute="_compute_orders_counts", string="Ordenes de venta"
    )
    location_dest_id = fields.Many2one("stock.location", "Locación destino")
    weighing_reception_id = fields.Many2one("weighing.reception", string="Recepción")
    reception_ids = fields.One2many(
        "weighing.reception",
        "weighing_reception_id",
        string="Recepciones",
    )
    reception_counts = fields.Integer(
        compute="_compute_reception_counts", string="Recepciones"
    )

    # Stat buttons and stat info counts

    def _compute_orders_counts(self):
        for rec in self:
            purchase_order_counts = self.env["purchase.order"].search_count(
                [("id", "=", rec.order_ids.ids)]
            )
            rec.purchase_order_counts = purchase_order_counts

    def action_open_orders(self):
        self.ensure_one()
        return {
            "name": _("Purchases"),
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "res_model": "purchase.order",
            "domain": [("id", "in", self.order_ids.ids)],
        }

    def _compute_reception_counts(self):
        for rec in self:
            reception_counts = self.env["weighing.reception"].search_count(
                [("id", "=", rec.reception_ids.ids)]
            )
            rec.reception_counts = reception_counts

    def action_open_receptions(self):
        self.ensure_one()
        return {
            "name": _("Receptions"),
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "res_model": "weighing.reception",
            "domain": [("id", "in", self.reception_ids.ids)],
        }

    @api.model
    def create(self, vals):
        """
        Create a new Weighing Reception with a sequence number.
        """
        vals.update(
            name=self.env["ir.sequence"].next_by_code("weighting.reception") or _("New")
        )
        return super(WeighingReception, self).create(vals)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """
        On change method triggered when the product_id field is modified.

        :param self: The current WeighingReception object.
        :return: None
        """
        for record in self:
            if record.product_id:
                record.product_name = record.product_id.name
            else:
                record.product_name = False

    @api.depends(
        "input_weight",
        "output_weight",
        "no_countable_desc",
        "qty_basket",
        "weight_basket",
        "basket_product_weight",
    )
    def _compute_product_weight(self):
        """
        Compute the weight of the product based on the difference
        between input and output weights.

        This method is triggered whenever the values of the
        "input_weight" or "output_weight" fields change. It updates
        the "product_weight" field with the computed weight.

        :param self: The current WeighingReception object.
        :return: None
        """
        for record in self:
            product_weight=0
            if (
                record.input_weight
                and record.output_weight
            ):
                    in_weight= record.input_weight
                    output = record.output_weight
                    bask_weight = record.basket_product_weight_unit * record.qty_basket
                    no_countable =record.no_countable_desc
                    product_weight = in_weight - output - bask_weight - no_countable

            # if record.weight_basket == True and record.basket_product_weight:
            #     multi_pw = product_weight * record.basket_product_weight
            #     product_weight = multi_pw
            # if record.no_countable_desc == True and record.basket_product_weight:
            #     product_weight = record.qty_basket - record.no_countable_desc
            # record.basket_product_weight = bask_weight
            record.product_weight = product_weight

    @api.depends("transfer_ids")
    def _compute_transfer_count(self):
        """
        Compute the number of transfers.
        """
        for record in self:
            record.transfer_count = len(record.transfer_ids.ids)

    def action_view_transfer(self):
        """
        Generates an action to view the transfers.

        :return: A dictionary representing the action to view the transfers.
        :rtype: dict
        """
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

    # State Actions

    def action_in(self):
        self.ensure_one()
        self.state = "in"

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
        """
        Creates a stock picking for transferring goods from a location to another.

        :return: The created stock picking.
        :rtype: stock.picking
        :raises: ValidationError if an error occurs during the creation of the stock picking.
        """
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
                        "product_uom_qty": self.qty_basket,
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
        """
        A description of the entire function, its parameters, and its return types.
        """
        self.ensure_one()
        pass
