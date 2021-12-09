# Copyright 2017 Comunitea Servicios Tecnológicos S.L.
# Copyright 2018 Eficent Business and IT Consulting Services, S.L.
# Copyright 2021 thingsintouch.com
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import logging

from odoo import _, api, models

from odoo import fields

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT

from datetime import datetime

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def register_attendance(self, card_code):
        res = super().register_attendance(card_code)

        if "action" in res:
            employee = self.search([("rfid_card_code", "=", card_code)], limit=1)
            last_attendance = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),], limit=1)

            if res["action"] == "check_in":
                res["action_msg"] = _("Checked in %s") % res["employee_name"]
                last_attendance.check_in_with_RAS = True

            elif res["action"] == "check_out":
                last_attendance.check_out_with_RAS = True
                res["action_msg"] = _("Checked out %s") % res["employee_name"]

            elif res["action"] == "FALSE":
                res["action_msg"] = _("Contact your admin")

        _logger.info(f"iot ras oca  models -- hr_employee -- res: {res}")
        return res

    def _attendance_action_change_timestamp(self, timestamp): # MODIFIED
        """ Check In/Check Out action
            Check In: create a new attendance record
            Check Out: modify check_out field of appropriate attendance record
        """
        self.ensure_one()

        try:
            timestamp_dt = datetime.fromtimestamp(int(timestamp), tz=None)  # ADDED
            action_date = datetime.strftime(timestamp_dt, DATETIME_FORMAT) # MODIFIED
            self._compute_attendance_state()

            if self.attendance_state != 'checked_in':
                vals = {
                    'employee_id': self.id,
                    'check_in': action_date,
                    'check_in_with_RAS': True,   # ADDED
                }
                return self.env['hr.attendance'].create(vals)

            attendance = self.env['hr.attendance'].search([('employee_id', '=', self.id), ('check_out', '=', False)], limit=1)
            if attendance:
                attendance.check_out = action_date
                attendance.check_out_with_RAS = True  # ADDED
            else:
                raise exceptions.UserError(_('Cannot perform check out on %(empl_name)s, could not find corresponding check in. '
                    'Your attendances have probably been modified manually by human resources.') % {'empl_name': self.sudo().name, })
                return False
            return attendance
        except Exception as e:
            _logger.error(e)
        return False

    @api.model
    def register_attendance_async(self, card_code_and_timestamp): # MODIFIED
        """Register the attendance of the employee.
        :returns: dictionary
            'rfid_card_code': char
            'employee_name': char
            'employee_id': int
            'error_message': char
            'logged': boolean
            'action': check_in/check_out
        """
        try:
            splitted  = card_code_and_timestamp.split("-")  # ADDED
            card_code = splitted[0]                         # ADDED
            timestamp = splitted[1]                         # ADDED
            res = {
                "rfid_card_code": card_code,
                "employee_name": "",
                "employee_id": False,
                "error_message": "",
                "logged": False,
                "action": "FALSE",
            }
            employee = self.search([("rfid_card_code", "=", card_code)], limit=1)
            if employee:
                res["employee_name"] = employee.name
                res["employee_id"] = employee.id
            else:
                msg = _("No employee found with card %s") % card_code
                _logger.warning(msg)
                res["error_message"] = msg
                return res
            try:
                attendance = employee._attendance_action_change_timestamp(timestamp) # MODIFIED
                if attendance:
                    msg = _("Attendance recorded for employee %s") % employee.name
                    _logger.debug(msg)
                    res["logged"] = True
                    if attendance.check_out:
                        res["action"] = "check_out"
                    else:
                        res["action"] = "check_in"
                    return res
                else:
                    msg = _("No attendance was recorded for employee %s") % employee.name
                    _logger.error(msg)
                    res["error_message"] = msg
                    return res
            except Exception as e:
                res["error_message"] = e
                _logger.error(e)
            return res
        except Exception as e:
            res["error_message"] = e
            _logger.error(e)
        return res


