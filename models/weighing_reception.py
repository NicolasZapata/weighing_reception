# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError

# State definitions list
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
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad de medida",
        compute="_onchange_uom",
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
    qty = fields.Float(string="Cantidad")
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Medida",
        compute="_onchange_uom",
        store=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        "Locación origen",
    )
    location_dest_id = fields.Many2one("stock.location", "Locación destino")
    no_countable_desc = fields.Float(string="Descontar el producto no conforme")
    weight_basket = fields.Boolean(string="Descontar Canastillas")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """
        This function is an onchange method that is triggered when 
        the value of the "product_id" field is changed.  It updates 
        the domain of the "categ_id" field based on the selected "product_id".

        :return: A dictionary containing the updated domain for the "categ_id" field.
        :rtype: dict
        """
        for record in self:
            return {
                "domain": {
                    "categ_id": [("product_id", "in", record.categ_id.id)],
                }
            }

    @api.depends("uom_id", "product_uom_id")
    def _onchange_uom(self):
        """
        Define a domain for uom_id field with the category of the product.

        This function is an onchange method that is triggered when the value 
        of the "uom_id" or "product_uom_id" field is changed. It updates the 
        domain of the "uom_id" and "product_uom_id" fields based on the 
        selected values.

        Parameters:
            self (RecordSet): The current recordset.

        Returns:
            None
        """
        self.ensure_one()
        if self.uom_id:
            self.product_uom_id = self.uom_id
        if self.product_uom_id:
            self.uom_id = self.product_uom_id

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

    @api.depends("input_weight", "output_weight")
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
            # Initialize the product weight to 0.0
            product_weight = 0.0
            # Check if both input and output weights are present
            if record.input_weight and record.output_weight:
                # Calculate the difference between input and output weights
                product_weight = record.input_weight - record.output_weight
            # Update the "product_weight" field with the computed weight
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
        """
        A description of the entire function, its parameters, and its return types.
        """
        self.ensure_one()
        pass
