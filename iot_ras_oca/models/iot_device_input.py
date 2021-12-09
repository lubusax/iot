# Copyright 2021 thingsintouch.com
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


class IotDeviceInput(models.Model):
    _inherit = "iot.device.input"


    @api.model
    def iot_ras_default_action(self, message):
        return {"action_msg": message, "action": "check_in"}

    @api.model
    def _call_device(self, value):
        res = super()._call_device(value)
        device = self.device_id
        device.last_connection = fields.Datetime.now()
        return res
