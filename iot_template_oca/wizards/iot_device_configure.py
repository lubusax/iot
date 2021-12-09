# Copyright 2020 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from uuid import uuid4

from odoo import _, api, fields, models

import logging

_logger = logging.getLogger(__name__)


class IotDeviceConfigure(models.TransientModel):
    _name = "iot.device.configure"
    _description = "Configure a IoT device"

    generated = fields.Boolean(default=False)
    serial = fields.Char(readonly=True)
    url = fields.Char(compute="_compute_url")
    url_short = fields.Char(compute="_compute_short_url")
    serial_short = fields.Char()

    @api.depends("serial")
    def _compute_url(self):
        for record in self:
            url = False
            if record.generated:
                _logger.info(f"iot_template_oca//wizards//iot_device_configure.py//_compute_url")
                _logger.info(f"_compute_url- record.serial {record.serial}, record.serial_short {record.serial_short}")
                url = (
                    self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                    + "/iot/"
                    + record.serial
                    + "/configure"
                )
            record.url = url

    @api.depends("serial")
    def _compute_short_url(self):
        for record in self:
            url_short = False
            if record.generated:
                record.serial_short = record.serial[:4]
                _logger.info(f"iot_template_oca//wizards//iot_device_configure.py//_compute_url")
                _logger.info(f"_compute_url- record.serial {record.serial}, record.serial_short {record.serial_short}")
                url_short = (
                    self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                    + "/iot/"
                    + record.serial_short
                    + "/conf"
                )
            record.url_short = url_short

    def run(self):
        _logger.info(f"iot_template_oca//wizards//iot_device_configure.py//run ")
        if not self.generated:
            self.write({"generated": True, "serial": uuid4()})
        return {
            "name": _("Configure device"),
            "type": "ir.actions.act_window",
            "res_model": "iot.device.configure",
            "view_mode": "form",
            "target": "new",
            "res_id": self.id,
            "context": self.env.context,
        }

    @api.model
    def configure(self, serial, template_id):
        config = self.search([("serial", "=", serial)])
        _logger.info(f"iot template oca//wizards//configure - serial {serial}, template_id {template_id}, config {config}")
        _logger.info(f"config.serial {config.serial} - config.serial_short {config.serial_short}")
        if not config:
            return {}
        config.unlink()
        device = self.env["iot.device"].create({"name": serial})
        template = self.env["iot.template"].search([("name", "=", template_id)])
        if template:
            _logger.info(f"iot template oca//wizards//configure - template {template}")
            template.apply_template(device, template._get_keys(serial))
        return device.get_iot_configuration()

    @api.model
    def configure_from_serial_short(self, serial_short, answer_from_device):
        config = self.search([("serial_short", "=", serial_short)])
        template_name = answer_from_device.get("template", False)
        _logger.info(f"iot template oca//wizards//configure - serial_short {serial_short}, template_name  {template_name }, config {config}")
        _logger.info(f"config.serial {config.serial} - config.serial_short {config.serial_short}")
        if not config:
            return {}
        else:
            serial = config.serial
        config.unlink()
        device = self.env["iot.device"].create({"name": serial})
        device.ip               = answer_from_device.get("ip", False)
        device.name             = "RAS-"+ serial_short
        device.last_connection  = fields.Datetime.now()
        device.setup_password   = answer_from_device.get("setup_password", False)
        template = self.env["iot.template"].search([("name", "=", template_name)])
        if template:
            _logger.info(f"iot template oca//wizards//configure - template {template}")
            template.apply_template(device, template._get_keys(serial))
        return device.get_iot_configuration()
