from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DisasterIncident(models.Model):
    _name = "dr.incident"
    _description = "Disaster Incident"
    _order = "start_date desc, id desc"

    name = fields.Char(required=True)
    code = fields.Char(required=True, copy=False, index=True)
    incident_type = fields.Selection(
        [
            ("flood", "Flood"),
            ("earthquake", "Earthquake"),
            ("storm", "Storm"),
            ("fire", "Fire"),
            ("outbreak", "Public Health Emergency"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    description = fields.Text()
    start_date = fields.Date(default=fields.Date.today, required=True)
    end_date = fields.Date()
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("closed", "Closed")],
        default="draft",
        required=True,
        index=True,
    )
    affected_area_ids = fields.One2many("dr.affected.area", "incident_id")
    camp_ids = fields.One2many("dr.relief.camp", "incident_id")
    request_ids = fields.One2many("dr.emergency.request", "incident_id")
    volunteer_team_ids = fields.Many2many(
        "dr.volunteer.team",
        "dr_incident_team_rel",
        "incident_id",
        "team_id",
        string="Volunteer Teams",
    )
    area_count = fields.Integer(compute="_compute_counts")
    camp_count = fields.Integer(compute="_compute_counts")
    request_count = fields.Integer(compute="_compute_counts")
    open_request_count = fields.Integer(compute="_compute_counts")

    _sql_constraints = [
        ("code_unique", "unique(code)", "Incident code must be unique."),
    ]

    @api.depends("affected_area_ids", "camp_ids", "request_ids", "request_ids.state")
    def _compute_counts(self):
        for record in self:
            record.area_count = len(record.affected_area_ids)
            record.camp_count = len(record.camp_ids)
            record.request_count = len(record.request_ids)
            record.open_request_count = len(
                record.request_ids.filtered(
                    lambda request: request.state
                    not in ("delivered", "rejected")
                )
            )

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for record in self:
            if record.end_date and record.end_date < record.start_date:
                raise ValidationError(_("The end date cannot precede the start date."))

    def action_activate(self):
        self.write({"state": "active"})

    def action_close(self):
        if any(
            request.state not in ("delivered", "rejected")
            for request in self.mapped("request_ids")
        ):
            raise UserError(_("Close all emergency requests before closing an incident."))
        self.write({"state": "closed", "end_date": fields.Date.today()})

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_open_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Emergency Requests"),
            "res_model": "dr.emergency.request",
            "view_mode": "kanban,list,form",
            "domain": [("incident_id", "=", self.id)],
            "context": {"default_incident_id": self.id},
        }


class DisasterAffectedArea(models.Model):
    _name = "dr.affected.area"
    _description = "Affected Area"
    _order = "priority desc, name"

    name = fields.Char(required=True)
    incident_id = fields.Many2one(
        "dr.incident", required=True, ondelete="cascade", index=True
    )
    location = fields.Char()
    population = fields.Integer(default=0)
    priority = fields.Selection(
        [("low", "Low"), ("normal", "Normal"), ("high", "High"), ("critical", "Critical")],
        default="normal",
        required=True,
    )
    status = fields.Selection(
        [("identified", "Identified"), ("assisted", "Assistance Underway"), ("stable", "Stable")],
        default="identified",
        required=True,
    )
    notes = fields.Text()
    camp_ids = fields.One2many("dr.relief.camp", "area_id")
    camp_count = fields.Integer(compute="_compute_camp_count")

    @api.depends("camp_ids")
    def _compute_camp_count(self):
        for record in self:
            record.camp_count = len(record.camp_ids)

    @api.constrains("population")
    def _check_population(self):
        if any(record.population < 0 for record in self):
            raise ValidationError(_("Population cannot be negative."))


class DisasterReliefCamp(models.Model):
    _name = "dr.relief.camp"
    _description = "Relief Camp"
    _order = "name"

    name = fields.Char(required=True)
    incident_id = fields.Many2one(
        "dr.incident", required=True, ondelete="cascade", index=True
    )
    area_id = fields.Many2one(
        "dr.affected.area",
        string="Affected Area",
        ondelete="restrict",
        domain="[('incident_id', '=', incident_id)]",
    )
    address = fields.Char()
    capacity = fields.Integer(default=0, required=True)
    occupancy = fields.Integer(default=0, required=True)
    available_capacity = fields.Integer(compute="_compute_available_capacity")
    manager_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    active = fields.Boolean(default=True)
    notes = fields.Text()

    @api.depends("capacity", "occupancy")
    def _compute_available_capacity(self):
        for record in self:
            record.available_capacity = record.capacity - record.occupancy

    @api.constrains("capacity", "occupancy")
    def _check_capacity(self):
        for record in self:
            if record.capacity < 0 or record.occupancy < 0:
                raise ValidationError(_("Camp capacity and occupancy cannot be negative."))
            if record.occupancy > record.capacity:
                raise ValidationError(_("Camp occupancy cannot exceed capacity."))

    @api.constrains("area_id", "incident_id")
    def _check_area_incident(self):
        for record in self:
            if record.area_id and record.area_id.incident_id != record.incident_id:
                raise ValidationError(_("The camp area must belong to the same incident."))


class DisasterResource(models.Model):
    _name = "dr.resource"
    _description = "Relief Resource"
    _order = "category, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, copy=False, index=True)
    category = fields.Selection(
        [
            ("food", "Food"),
            ("water", "Water"),
            ("medical", "Medical"),
            ("shelter", "Shelter"),
            ("clothing", "Clothing"),
            ("hygiene", "Hygiene"),
            ("equipment", "Equipment"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    uom = fields.Char(string="Unit of Measure", required=True, default="Unit")
    location = fields.Char()
    quantity_on_hand = fields.Float(required=True, default=0)
    quantity_reserved = fields.Float(readonly=True, default=0)
    quantity_available = fields.Float(
        compute="_compute_quantity_available", string="Available Quantity", store=True
    )
    reorder_level = fields.Float(default=0)
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _sql_constraints = [
        ("code_unique", "unique(code)", "Resource code must be unique."),
    ]

    @api.depends("quantity_on_hand", "quantity_reserved")
    def _compute_quantity_available(self):
        for record in self:
            record.quantity_available = record.quantity_on_hand - record.quantity_reserved

    @api.constrains("quantity_on_hand", "quantity_reserved", "reorder_level")
    def _check_quantities(self):
        for record in self:
            if (
                record.quantity_on_hand < 0
                or record.quantity_reserved < 0
                or record.reorder_level < 0
            ):
                raise ValidationError(_("Resource quantities cannot be negative."))
            if record.quantity_reserved > record.quantity_on_hand:
                raise ValidationError(
                    _("Reserved quantity cannot exceed quantity on hand.")
                )

    def action_adjust_stock(self):
        """Open the resource in a form where an authorized user can adjust stock."""
        return {
            "type": "ir.actions.act_window",
            "name": _("Adjust Resource Stock"),
            "res_model": "dr.resource",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }

    def unlink(self):
        if any(resource.quantity_reserved for resource in self):
            raise UserError(_("Resources with active reservations cannot be deleted."))
        return super().unlink()

    def _lock_quantities(self):
        self.ensure_one()
        self.env.cr.execute(
            "SELECT quantity_on_hand, quantity_reserved "
            "FROM dr_resource WHERE id = %s FOR UPDATE",
            (self.id,),
        )
        row = self.env.cr.fetchone()
        if not row:
            raise UserError(_("The resource no longer exists."))
        return row

    def _reserve(self, quantity):
        self.ensure_one()
        if quantity <= 0:
            raise ValidationError(_("The quantity to reserve must be positive."))
        # Lock the row so two concurrent allocations cannot reserve the same stock.
        on_hand, reserved = self._lock_quantities()
        available = on_hand - reserved
        if quantity > available:
            raise UserError(
                _(
                    "Not enough %(resource)s in stock. Available: %(available).2f %(uom)s.",
                    resource=self.display_name,
                    available=available,
                    uom=self.uom,
                )
            )
        self.write({"quantity_reserved": reserved + quantity})

    def _release_reserved(self, quantity):
        self.ensure_one()
        if quantity < 0:
            raise ValidationError(_("The quantity to release cannot be negative."))
        _on_hand, reserved = self._lock_quantities()
        new_reserved = max(0, reserved - quantity)
        self.write({"quantity_reserved": new_reserved})

    def _consume_reserved(self, quantity):
        self.ensure_one()
        on_hand, reserved = self._lock_quantities()
        if quantity <= 0 or quantity > reserved:
            raise ValidationError(_("Consumed quantity must be within the reserved stock."))
        self.write(
            {
                "quantity_reserved": reserved - quantity,
                "quantity_on_hand": on_hand - quantity,
            }
        )


class DisasterEmergencyRequest(models.Model):
    _name = "dr.emergency.request"
    _description = "Emergency Resource Request"
    _order = "priority desc, request_date desc, id desc"

    name = fields.Char(required=True, copy=False, default="New", index=True)
    incident_id = fields.Many2one(
        "dr.incident", required=True, ondelete="restrict", index=True
    )
    affected_area_id = fields.Many2one(
        "dr.affected.area",
        string="Affected Area",
        ondelete="restrict",
        domain="[('incident_id', '=', incident_id)]",
    )
    camp_id = fields.Many2one(
        "dr.relief.camp",
        string="Destination Camp",
        ondelete="restrict",
        domain="[('incident_id', '=', incident_id)]",
    )
    requester_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    request_date = fields.Datetime(default=fields.Datetime.now, required=True)
    priority = fields.Selection(
        [("low", "Low"), ("normal", "Normal"), ("high", "High"), ("critical", "Critical")],
        default="normal",
        required=True,
        index=True,
    )
    description = fields.Text()
    state = fields.Selection(
        [
            ("requested", "Requested"),
            ("under_review", "Under Review"),
            ("approved", "Approved"),
            ("resources_allocated", "Resources Allocated"),
            ("dispatched", "Dispatched"),
            ("delivered", "Delivered"),
            ("rejected", "Rejected"),
        ],
        default="requested",
        required=True,
        index=True,
    )
    request_line_ids = fields.One2many(
        "dr.emergency.request.line", "request_id", string="Requested Resources"
    )
    delivery_ids = fields.One2many("dr.delivery", "request_id")
    total_requested = fields.Float(compute="_compute_totals", store=True)
    total_allocated = fields.Float(compute="_compute_totals", store=True)
    total_delivered = fields.Float(compute="_compute_totals", store=True)
    delivery_count = fields.Integer(compute="_compute_totals", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "dr.emergency.request"
                ) or "New"
        return super().create(vals_list)

    @api.depends(
        "request_line_ids.quantity",
        "request_line_ids.allocated_qty",
        "request_line_ids.delivered_qty",
        "delivery_ids",
    )
    def _compute_totals(self):
        for record in self:
            record.total_requested = sum(record.request_line_ids.mapped("quantity"))
            record.total_allocated = sum(record.request_line_ids.mapped("allocated_qty"))
            record.total_delivered = sum(record.request_line_ids.mapped("delivered_qty"))
            record.delivery_count = len(record.delivery_ids)

    @api.constrains("affected_area_id", "camp_id", "incident_id")
    def _check_destinations(self):
        for record in self:
            if (
                record.affected_area_id
                and record.affected_area_id.incident_id != record.incident_id
            ):
                raise ValidationError(_("The affected area must belong to the incident."))
            if record.camp_id and record.camp_id.incident_id != record.incident_id:
                raise ValidationError(_("The destination camp must belong to the incident."))

    def _ensure_lines(self):
        if any(not request.request_line_ids for request in self):
            raise UserError(_("Add at least one resource line before continuing."))

    def unlink(self):
        if any(request.state in ("resources_allocated", "dispatched", "delivered") for request in self):
            raise UserError(_("Allocated or delivered requests cannot be deleted."))
        return super().unlink()

    def action_submit(self):
        self._ensure_lines()
        self.write({"state": "requested"})

    def action_under_review(self):
        if any(request.state != "requested" for request in self):
            raise UserError(_("Only requested requests can be moved under review."))
        self.write({"state": "under_review"})

    def action_approve(self):
        self._ensure_lines()
        if any(request.state != "under_review" for request in self):
            raise UserError(_("Only requests under review can be approved."))
        self.write({"state": "approved"})

    def action_allocate(self):
        self._ensure_lines()
        for request in self:
            if request.state != "approved":
                raise UserError(_("Only approved requests can allocate resources."))
            for line in request.request_line_ids:
                if line.allocated_qty:
                    raise UserError(_("This request has already been allocated."))
                line.resource_id._reserve(line.quantity)
                line.allocated_qty = line.quantity
            request.state = "resources_allocated"

    def action_dispatch(self):
        for request in self:
            if request.state != "resources_allocated":
                raise UserError(_("Only allocated requests can be dispatched."))
            if not request.delivery_ids:
                self.env["dr.delivery"].create(
                    {
                        "request_id": request.id,
                        "incident_id": request.incident_id.id,
                        "camp_id": request.camp_id.id,
                        "state": "dispatched",
                        "dispatched_at": fields.Datetime.now(),
                    }
                )
            request.state = "dispatched"

    def action_reject(self):
        for request in self:
            if request.state in ("delivered", "rejected"):
                continue
            if request.state in ("resources_allocated", "dispatched"):
                for line in request.request_line_ids:
                    if line.allocated_qty > line.delivered_qty:
                        line.resource_id._release_reserved(
                            line.allocated_qty - line.delivered_qty
                        )
                    line.allocated_qty = 0
            request.state = "rejected"

    def _complete_delivery(self):
        self.ensure_one()
        if self.state != "dispatched":
            raise UserError(_("Only dispatched requests can be delivered."))
        for line in self.request_line_ids:
            quantity = line.allocated_qty - line.delivered_qty
            if quantity <= 0:
                continue
            line.resource_id._consume_reserved(quantity)
            line.delivered_qty += quantity
        self.state = "delivered"

    def action_open_deliveries(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Deliveries"),
            "res_model": "dr.delivery",
            "view_mode": "list,form",
            "domain": [("request_id", "=", self.id)],
            "context": {"default_request_id": self.id},
        }


class DisasterEmergencyRequestLine(models.Model):
    _name = "dr.emergency.request.line"
    _description = "Emergency Request Line"
    _order = "id"

    request_id = fields.Many2one(
        "dr.emergency.request", required=True, ondelete="cascade"
    )
    resource_id = fields.Many2one("dr.resource", required=True, ondelete="restrict")
    quantity = fields.Float(required=True, default=1)
    allocated_qty = fields.Float(readonly=True, default=0)
    delivered_qty = fields.Float(readonly=True, default=0)
    remaining_qty = fields.Float(compute="_compute_remaining")
    uom = fields.Char(related="resource_id.uom", readonly=True)

    @api.depends("quantity", "delivered_qty")
    def _compute_remaining(self):
        for record in self:
            record.remaining_qty = record.quantity - record.delivered_qty

    @api.constrains("quantity", "allocated_qty", "delivered_qty")
    def _check_quantities(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_("Requested quantity must be positive."))
            if record.delivered_qty < 0 or record.allocated_qty < 0:
                raise ValidationError(_("Allocated and delivered quantities cannot be negative."))
            if record.allocated_qty > record.quantity:
                raise ValidationError(_("Allocated quantity cannot exceed requested quantity."))
            if record.delivered_qty > record.allocated_qty:
                raise ValidationError(_("Delivered quantity cannot exceed allocated quantity."))

    def write(self, vals):
        editable_after_review = {"allocated_qty", "delivered_qty"}
        for record in self:
            if record.request_id.state not in ("requested", "under_review"):
                if set(vals) - editable_after_review:
                    raise UserError(
                        _("Requested resources cannot be edited after approval.")
                    )
            if "quantity" in vals and record.allocated_qty:
                raise UserError(
                    _("Allocated quantities cannot be changed; reject the request instead.")
                )
        return super().write(vals)

    def unlink(self):
        if any(line.request_id.state not in ("requested", "under_review") for line in self):
            raise UserError(_("Request lines cannot be deleted after review starts."))
        return super().unlink()


class DisasterVolunteer(models.Model):
    _name = "dr.volunteer"
    _description = "Volunteer"
    _order = "name"

    name = fields.Char(required=True)
    phone = fields.Char()
    email = fields.Char()
    skill_ids = fields.Many2many(
        "dr.volunteer.skill",
        "dr_volunteer_skill_rel",
        "volunteer_id",
        "skill_id",
        string="Skills",
    )
    availability = fields.Selection(
        [("available", "Available"), ("deployed", "Deployed"), ("unavailable", "Unavailable")],
        default="available",
        required=True,
    )
    notes = fields.Text()
    active = fields.Boolean(default=True)


class DisasterVolunteerSkill(models.Model):
    _name = "dr.volunteer.skill"
    _description = "Volunteer Skill"
    _order = "name"

    name = fields.Char(required=True)
    description = fields.Text()
    volunteer_ids = fields.Many2many(
        "dr.volunteer",
        "dr_volunteer_skill_rel",
        "skill_id",
        "volunteer_id",
        string="Volunteers",
    )

    _sql_constraints = [
        ("name_unique", "unique(name)", "Skill names must be unique."),
    ]


class DisasterVolunteerTeam(models.Model):
    _name = "dr.volunteer.team"
    _description = "Volunteer Team"
    _order = "name"

    name = fields.Char(required=True)
    leader_id = fields.Many2one("dr.volunteer")
    member_ids = fields.Many2many("dr.volunteer", string="Members")
    incident_ids = fields.Many2many(
        "dr.incident",
        "dr_incident_team_rel",
        "team_id",
        "incident_id",
        string="Incidents",
    )
    status = fields.Selection(
        [("forming", "Forming"), ("ready", "Ready"), ("deployed", "Deployed"), ("closed", "Closed")],
        default="forming",
        required=True,
    )
    notes = fields.Text()

    @api.constrains("leader_id", "member_ids")
    def _check_leader(self):
        for record in self:
            if record.leader_id and record.leader_id not in record.member_ids:
                raise ValidationError(_("The team leader must be one of the team members."))


class DisasterDelivery(models.Model):
    _name = "dr.delivery"
    _description = "Relief Delivery"
    _order = "dispatched_at desc, id desc"

    name = fields.Char(required=True, copy=False, default="New", index=True)
    request_id = fields.Many2one(
        "dr.emergency.request", required=True, ondelete="restrict", index=True
    )
    incident_id = fields.Many2one(
        "dr.incident", required=True, ondelete="restrict", index=True
    )
    camp_id = fields.Many2one(
        "dr.relief.camp",
        string="Destination Camp",
        ondelete="restrict",
        domain="[('incident_id', '=', incident_id)]",
    )
    state = fields.Selection(
        [("pending", "Pending"), ("dispatched", "Dispatched"), ("delivered", "Delivered")],
        default="pending",
        required=True,
        index=True,
    )
    dispatched_at = fields.Datetime()
    delivered_at = fields.Datetime()
    received_by = fields.Char()
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("dr.delivery") or "New"
            if vals.get("request_id") and not vals.get("incident_id"):
                request = self.env["dr.emergency.request"].browse(vals["request_id"])
                vals["incident_id"] = request.incident_id.id
                vals.setdefault("camp_id", request.camp_id.id)
        return super().create(vals_list)

    @api.constrains("request_id", "incident_id", "camp_id")
    def _check_relations(self):
        for record in self:
            if record.request_id.incident_id != record.incident_id:
                raise ValidationError(_("The delivery incident must match its request."))
            if record.camp_id and record.camp_id.incident_id != record.incident_id:
                raise ValidationError(_("The delivery camp must belong to the incident."))

    def action_mark_dispatched(self):
        for record in self:
            if record.state != "pending":
                continue
            if record.request_id.state != "resources_allocated":
                raise UserError(_("The request must be allocated before dispatch."))
            record.write({"state": "dispatched", "dispatched_at": fields.Datetime.now()})
            record.request_id.state = "dispatched"

    def unlink(self):
        if any(record.state == "delivered" for record in self):
            raise UserError(_("Delivered records cannot be deleted."))
        return super().unlink()

    def action_mark_delivered(self):
        for record in self:
            if record.state == "delivered":
                continue
            if record.state != "dispatched":
                raise UserError(_("Only dispatched deliveries can be marked delivered."))
            record.request_id._complete_delivery()
            record.write({"state": "delivered", "delivered_at": fields.Datetime.now()})
