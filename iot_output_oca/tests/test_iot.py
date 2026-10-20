# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestIoT(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.system = cls.env["iot.communication.system"].create({"name": "Testing"})
        cls.system_2 = cls.env["iot.communication.system"].create(
            {"name": "Testing 02"}
        )
        cls.action = cls.env["iot.communication.system.action"].create(
            {"name": "test", "communication_system_id": cls.system.id}
        )
        cls.action_2 = cls.env["iot.communication.system.action"].create(
            {"name": "test 02", "communication_system_id": cls.system_2.id}
        )
        cls.device = cls.env["iot.device"].create({"name": "Device"})
        cls.output = cls.env["iot.device.output"].create(
            {
                "communication_system_id": cls.system.id,
                "device_id": cls.device.id,
                "name": "Output",
            }
        )

    def test_views(self):
        self.assertEqual(self.device.output_count, 1)
        res = self.device.action_show_output()
        self.assertEqual(self.output, self.env[res["res_model"]].browse(res["res_id"]))

    def test_action(self):
        self.assertEqual(self.output.action_count, 0)
        with mute_logger("odoo.addons.iot_oca.models.iot_communication_system_action"):
            self.output.with_context(
                iot_communication_system_action_id=self.action.id
            ).device_run_action()
        self.assertEqual(self.output.action_count, 1)
        self.assertEqual(self.output.action_ids.status, "failed")

    def test_action_archived_device(self):
        self.assertEqual(self.output.action_count, 0)
        self.device.active = False
        with mute_logger("odoo.addons.iot_oca.models.iot_communication_system_action"):
            self.output.with_context(
                iot_communication_system_action_id=self.action.id
            ).device_run_action()
        self.assertEqual(self.output.action_count, 0)

    def test_correct_action(self):
        self.assertEqual(self.output.action_count, 0)
        with patch(
            "odoo.addons.iot_oca.models.iot_communication_system_action."
            "IoTSystemAction._run",
            return_value=("ok", ""),
        ):
            self.output.with_context(
                iot_communication_system_action_id=self.action.id
            ).device_run_action()
        self.assertEqual(self.output.action_count, 1)
        self.assertEqual(self.output.action_ids.status, "ok")

    def test_constrains(self):
        with self.assertRaises(ValidationError):
            self.output.with_context(
                iot_communication_system_action_id=self.action_2.id
            ).device_run_action()
