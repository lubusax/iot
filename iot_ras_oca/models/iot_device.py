# Copyright 2021 thingsintouch.com
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models

# from odoo.addons.base.res.res_partner import _tz_get # <= odoo 11.0
from odoo.addons.base.models.res_partner import _tz_get # >= odoo 12.0

import logging

_logger = logging.getLogger(__name__)

class IotDevice(models.Model):
    _inherit = "iot.device"

    something_to_send =  fields.Boolean("RAS Device Parameter was changed",
        required = True,
        default = True)

    last_connection = fields.Datetime('Last Connection',
        help = "Timestamp of the last successful connection between the Device and Odoo",
        default = None,
        readonly = True)

    minimumTimeBetweenClockings = fields.Integer(string='Minimum Time between Clockings [s]',
        required=True,
        default= 300,
        help="How long is clocking again blocked [s]")

    period_odoo_routine_check =  fields.Integer(string='Time between Routine checks [s]',
        required=True,
        default= 12,
        help="How long between every information exchange from Odoo to Terminal RAS [s]")

    period_register_clockings =  fields.Integer(string='Time between Registering Clockings [s]',
        required=True,
        default= 15,
        help="How long between sending the locally stored Clockings on the RAS to Odoo [s]")

    tz = fields.Selection(
        _tz_get, string='Timezone', required=True,
        default=lambda self: self._context.get('tz') or self.env.user.tz or 'Europe/Berlin',
        help="In which timezone the Device will display time.")

    time_format = fields.Selection(
        [("12 hour","12 hour"),("24 hour","24 hour")],
        string='12 or 24-hour',
        required=True,
        default= "12 hour",
        help="am/pm or 00:00 to 23:59")

    card_registered = fields.Char("Text Display for 'clocking registered'",
        default = "Registered",
        help = "Text to show on Display when card is registered for async clocking")

    too_little_time_between_clockings = fields.Char("Text Display for 'too little time between clockings'",
        default = "Too Soon",
        help = "Text to show on Display when card is not registered for async clocking because there was too little time between card swipes")

    setup_password = fields.Char("Setup Password (Terminal)",
        help = "Password needed to introduce new Parameters (SSID, Odoo URL) during the Setup of the Terminal")

    timeToDisplayResultAfterClocking = fields.Float(string='How Long Display Text shown [s]',
        required=True,
        default= 1.2,
        help="How Long will the Display show the Result after Clocking [s]")

    shouldGetFirmwareUpdate = fields.Boolean("Update Firmware and Reboot (now)",
        required=True,
        default= False,
        help = "Update the firmware after rebooting")

    shutdownTerminal = fields.Boolean("Shutdown (Turn Off the Terminal)",
        help = "Shutdown the Terminal immediately",
        default = False)

    rebootTerminal = fields.Boolean("Reboot Now",
        help = "Reboot the Terminal immediately (Turn Off the Terminal and again On)",
        default = False)

    partialFactoryReset = fields.Boolean("Partial Factory Reset",
        help = "Locally Stored Clockings will be preserved (will NOT be deleted)",
        default = False)

    fullFactoryReset = fields.Boolean("Full Factory Reset",
        help = "Locally Stored Clockings will be deleted",
        default = False)

    # @api.onchange('fullFactoryReset', 'partialFactoryReset', 'rebootTerminal', 'shutdownTerminal',
    # 'shouldGetFirmwareUpdate', 'timeToDisplayResultAfterClocking', 'setup_password', 'too_little_time_between_clockings',
    # 'card_registered', 'time_format', 'tz', 'period_register_clockings', 'period_odoo_routine_check',
    # 'minimumTimeBetweenClockings', 'name')
    # @api.onchange('name')
    # def RAS_parameter_changed(self):
    #     self.ensure_one()
    #     _logger.info("**************************************** RAS Parameter changed")
    #     self.something_to_send = True
