# Copyright 2021 thingsintouch.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from odoo import fields, http

import logging

_logger = logging.getLogger(__name__)

boolean_flags = [
    "shouldGetFirmwareUpdate",
    "shutdownTerminal",
    "rebootTerminal",
    "partialFactoryReset",
    "fullFactoryReset",
]

class RAS_Routine(http.Controller):

    @http.route(
        ["/iot/<serial>/ras_routine"],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def ras_routine_iot(self, serial, *args, **kwargs):

        def set_boolean_flags_to_false(device):
            for flag in boolean_flags:
                device[flag] = False

        def answer_ras_routine_call(device):
            answer = {
                "card_registered"                   : device.card_registered,
                "too_little_time_between_clockings" : device.too_little_time_between_clockings,
                "minimumTimeBetweenClockings"       : device.minimumTimeBetweenClockings,

                "setup_password"                    : device.setup_password,
                "tz"                                : device.tz,
                "time_format"                       : device.time_format,
                "period_odoo_routine_check"         : device.period_odoo_routine_check,
                "period_register_clockings"         : device.period_register_clockings,

                "timeToDisplayResultAfterClocking"  : device.timeToDisplayResultAfterClocking,
                "shouldGetFirmwareUpdate"           : device.shouldGetFirmwareUpdate,
                "shutdownTerminal"                  : device.shutdownTerminal,
                "rebootTerminal"                    : device.rebootTerminal,

                "partialFactoryReset"               : device.partialFactoryReset,
                "fullFactoryReset"                  : device.fullFactoryReset,
                "RASxxx"                            : device.name,
            }
            return answer

        request = http.request
        _logger.info(f"ras_routine_iot - serial {serial}, *args {args}, **kwargs {kwargs}")

        res = False

        if request.env:
            input_ = (
                request.env["iot.device.input"]
                .sudo()
                .get_device(serial, kwargs["passphrase"])
            )
            device = request.env['iot.device'].sudo().search([
                ('input_ids', '=', input_.id),], limit=1)

            if device:
                device.last_connection =  fields.Datetime.now()
                res = answer_ras_routine_call(device)
                set_boolean_flags_to_false(device)

        json_res = json.dumps(res)
        _logger.info(f"ras_routine_iot - response json_res {json_res}")
        return json_res



