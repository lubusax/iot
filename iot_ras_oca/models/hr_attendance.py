# Copyright 2021 thingsintouch.com
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import logging

from odoo import api, fields, models
_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):

    _inherit = "hr.attendance"

    check_in_with_RAS = fields.Boolean( string="Used an RFID Attendance Terminal to check-in?",
                                        default=False,
                                        required=True)
    check_out_with_RAS = fields.Boolean( string="Used an RFID Attendance Terminal to check-out?",
                                        default=False,
                                        required=True)

    @api.onchange('check_in')
    def changed_check_in_not_using_RAS(self):
        self.check_in_with_RAS = False

    @api.onchange('check_out')
    def changed_check_out_not_using_RAS(self):
        self.check_out_with_RAS = False

