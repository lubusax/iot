# Copyright 2020 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from odoo import http

import logging

_logger = logging.getLogger(__name__)


class CallIot(http.Controller):
    @http.route(
        ["/iot/<serial>/configure"],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def configure_iot(self, serial, *args, **kwargs):
        request = http.request
        _logger.info(f"iot template oca//iot_controller//configure_iot - serial {serial}, *args {args}, **kwargs {kwargs}")
        template = kwargs.get("template", False)
        if not request.env:
            return json.dumps(False)
        json_res = json.dumps(
            request.env["iot.device.configure"].sudo().configure(serial, template)
        )
        _logger.info(f"iot template oca//iot_controller//configure_iot - response json_res {json_res}")
        return json_res

    @http.route(
        ["/iot/<serial_short>/conf"],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def configure_iot_from_serial_short(self, serial_short, *args, **answer_from_device):
        request = http.request
        _logger.info(f"iot template oca//iot_controller//configure_iot - serial_short {serial_short}, *args {args}, **answer_from_device {answer_from_device}")
        # template = kwargs.get("template", False)
        if not request.env:
            return json.dumps(False)
        json_res = json.dumps(
            request.env["iot.device.configure"].sudo().configure_from_serial_short(serial_short, answer_from_device)
        )
        _logger.info(f"iot template oca//iot_controller//configure_iot - response json_res {json_res}")
        return json_res
