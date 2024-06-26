# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError

# State definitions list
_STATES = [
    ("draft", "New"),
    ("in", "Input"),
    ("out", "Exit"),
    ("selection", "Selection"),
    ("received", "Received"),
]

PROCUREMENT_PRIORITIES = [("0", "Normal"), ("1", "Urgent")]


class WeighingReception(models.Model):
    _name = "weighing.reception"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Weighing Reception"
    _order = "id desc"

    priority = fields.Selection(
        PROCUREMENT_PRIORITIES,
        string="Priority",
        default="0",
        help="Receptions will be reserved first for the transfers with the highest priorities.",
    )
    name = fields.Char(default="New", required=False)
    state = fields.Selection(_STATES, string="State", default="draft")
    vehicle_license_plate = fields.Char(string="Placa vehículo")
    datetime_in = fields.Datetime(string="Fecha/hora recepción")
    datetime_out = fields.Datetime(string="Fecha/hora salida")
    employee_id = fields.Many2one(
        "hr.employee", string="Receptor", default=lambda self: self.env.user.employee_id
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
        default=lambda self: self.env.ref("product.product_category_all").id,
    )
    product_name = fields.Char("Descripción")
    description = fields.Html("Description", translate=True)
    # ----------------------------- Uom | Unidades de Medidas -------------------------------------------------
    standar_uom_weight_name = fields.Char(
        "uom.uom",
        related="product_id.weight_uom_name",
        store=True,
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Medida del producto",
        related="product_id.uom_id",
        store=True,
    )
    # ----------------------------- basket | canastillas -------------------------------------------------
    qty_basket = fields.Float(string="Cantidad de canastillas")
    basket_uom_name = fields.Char(
        string="Medida de Canastilla",
        related="basket_product_id.weight_uom_name",
    )
    basket_product_weight_unit = fields.Float(
        string="Peso Unitario de canastillas", related="basket_product_id.weight"
    )
    basket_product_weight = fields.Float(string="Peso neto de canastillas")
    weight_basket = fields.Boolean(string="Descontar Canastillas", default=False)
    basket_product_id = fields.Many2one(
        "product.product", string="Producto de Canastilla"
    )
    # ----------------------- Not countable | Producto No Conforme ----------------------------------------
    discount_product = fields.Boolean(string="Aplicar descuento del producto")
    not_countable_weight = fields.Float(string="Peso de producto no conforme")
    not_countable_weight_uom_name = fields.Char(
        string="Medida de producto no conforme", related="product_id.weight_uom_name"
    )
    no_countable_desc = fields.Float(string="Producto no conforme")
    # ----------------------- Res Partner Model Fields ----------------------------------------
    farmer_id = fields.Many2one(
        "res.partner", string="Agricultor", required=True, tracking=True
    )
    driver_id = fields.Many2one("res.partner", string="Conductor")
    supplier_id = fields.Many2one("res.partner", string="Proveedor")
    # ----------------------- Order Model ----------------------------------------
    order_ids = fields.One2many(
        "purchase.order",
        "weighing_reception_id",
        string="Ordenes de compra",
    )
    purchase_order_counts = fields.Integer(compute="_compute_orders_counts")
    check_weighning = fields.Boolean(string="Check Weighing", default=False)
    check_user = fields.Boolean(compute="_compute_check_user")

    # Computed Files (Normal Fields) and Created Files (Related Fields)

    def _compute_check_user(self):
        """
        Compute the value of the 'check_user' field based on the user's group membership.

        This method checks if the current user belongs to the 'weighing_reception.group_weighing_reception_admin' group.
        If the user is a member of the group, the 'check_user' field is set to True.
        Otherwise, the 'check_user' field is set to False.

        Parameters:
            self: The current instance of the class.
        """
        if self.user_has_groups("weighing_reception.group_weighing_reception_admin"):
            self.check_user = True
        else:
            self.check_user = False

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
        "input_weight",  # Weight of the product at the entrance
        "output_weight",  # Weight of the product at the exit
        "not_countable_weight",  # Weight of the product that is not countable
        "qty_basket",  # Quantity of baskets
        "weight_basket",  # Weight of a basket
        "basket_product_weight",  # Weight of the product in a basket
    )
    def _compute_product_weight(self):
        """
        Compute the weight of the product.

        The weight of the product is computed by subtracting the weight
        of the product at the exit, the weight of the product in baskets,
        and the weight of the product that is not countable, from the weight
        of the product at the entrance.
        """
        for record in self:
            # Initialize the weight of the product
            product_weight = 0
            bask_weight = 0
            # If the weight of the product at the entrance and the weight of
            # the product at the exit are available
            if record.input_weight and record.output_weight:
                in_weight = record.input_weight  # Weight at the entrance
                output = record.output_weight  # Weight at the exit
                bask_weight = (
                    record.basket_product_weight_unit * record.qty_basket
                )  # Weight of the product in baskets
                no_countable = (
                    record.not_countable_weight
                )  # Weight of the product that is not countable
                # Compute the weight of the product
                product_weight = in_weight - output - bask_weight - no_countable
            # Set the computed weight of the product
            record.product_weight = product_weight
            record.basket_product_weight = bask_weight

    # Order's Models Methods

    def _compute_orders_counts(self):
        for record in self:
            record.purchase_order_counts = len(record.order_ids.ids)

    def action_open_orders(self):
        action = {
            "name": _("Recepciones"),
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "context": {"create": False},
        }
        if len(self.order_ids) == 1:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": self.order_ids.id,
                }
            )
        else:
            action.update(
                {
                    "view_mode": "list,form",
                    "domain": [("id", "in", self.order_ids.ids)],
                }
            )
        return action

    def action_order(self):
        """
        Creates a purchase order for the current farmer and product.

        This method ensures that there is only one record in the current recordset
        before proceeding with the order creation. It then creates a dictionary
        `vals` with the necessary information for the purchase order. The `vals`
        dictionary includes the farmer's partner ID, an order line with the product
        ID, product name, and quantity.

        After creating the purchase order using the `vals` dictionary, the method
        adds the created order to the `order_ids` field of the current recordset.

        If any exception occurs during the order creation, a `ValidationError` is
        raised with the error message.

        :return: The created purchase order.
        :rtype: purchase.order
        :raises: ValidationError if an error occurs during the order creation.
        """
        self.ensure_one()
        vals = {
            "partner_id": self.supplier_id.id,
            "origin": self.name,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product_id.id,
                        "name": self.product_name,
                        "product_qty": self.product_weight,
                    },
                )
            ],
        }
        try:
            order_id = self.env["purchase.order"].sudo().create(vals)
            self.order_ids += order_id
            self.state = "received"
        except Exception as e:
            raise ValidationError(_(e))

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

    def action_print(self):
        """
        A description of the entire function, its parameters, and its return types.
        """
        self.ensure_one()
        return self.env.ref(
            "weighing_reception.action_weighing_reception_report"
        ).read()[0]
