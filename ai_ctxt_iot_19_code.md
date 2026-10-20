### File: `iot_input_oca/controller/__init__.py`
```python
from . import iot_input_controller

```

### File: `iot_input_oca/controller/iot_input_controller.py`
```python
# Copyright 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging

from odoo import _, http

_logger = logging.getLogger(__name__)


class CallIot(http.Controller):
    @http.route(
        ["/iot/<serial>/action"],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def call_unauthorized_iot(self, serial, passphrase=False, *args, **kwargs):
        request = http.request
        if not request.env:
            return json.dumps(False)
        return json.dumps(
            request.env["iot.device.input"]
            .sudo()
            .get_device(serial, passphrase)
            .call_device(**kwargs)
        )

    @http.route(
        ["/iot/<serial>/multi_input"],
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def call_unauthorized_iot_multi_input(
        self, serial, passphrase=False, values=False, *args, **kwargs
    ):
        """Controller to write multiple input data to device inputs

        :param string passphrase:
            Device passphrase in POST data.

        :param string values:
            JSON formatted string containing a JSON an array of JSON objects.
        """
        request = http.request
        if not request.env:
            _logger.warning("env not set")
            return json.dumps({"status": "error", "message": _("Server Error")})
        if not passphrase:
            _logger.warning("Passphrase is required")
            return json.dumps(
                {"status": "error", "message": _("Passphrase is required")}
            )
        if not values:
            _logger.warning("Values is required")
            return json.dumps({"status": "error", "message": _("Values is required")})
        # Decode JSON object here and use pure python objects in further calls
        try:
            if isinstance(values, str):
                values = json.loads(values)
            if not isinstance(values, list):
                raise SyntaxError
        except json.decoder.JSONDecodeError:
            _logger.warning("Values is not a valid JSON")
            return json.dumps(
                {"status": "error", "message": _("Values is not a valid JSON")}
            )
        except SyntaxError:
            _logger.warning("Values should be a JSON array of JSON objects")
            return json.dumps(
                {
                    "status": "error",
                    "message": _("Values should be a JSON array of JSON objects"),
                }
            )
        # Encode response to JSON and return
        result = (
            request.env["iot.device.input"]
            .sudo()
            .get_device(serial, passphrase)
            .call_device(values=values)
        )
        if result["status"] != "ok":
            return json.dumps({"status": result["status"]})
        return json.dumps(result["result"])

    @http.route(
        ["/iot/<serial>/check"], type="http", auth="none", methods=["POST"], csrf=False
    )
    def check_unauthorized_iot(self, serial, *args, **kwargs):
        request = http.request
        if not request.env:
            return json.dumps(False)
        device = (
            request.env["iot.device.input"]
            .sudo()
            .get_device(serial, kwargs["passphrase"])
        )
        if device:
            return json.dumps({"state": True})
        return json.dumps({"state": False})

```

### File: `iot_input_oca/examples/multi_input_values.json`
```text
[
  {
    "address": "ZMPT101B_1",
    "value": 230
  },
  {
    "address": 1,
    "value": true
  },
  {
    "address": 2,
    "value": "Door opened",
    "uuid": "abcde"
  },
  {
    "address": 10,
    "value": -18.5
  }
]

```

### File: `iot_input_oca/__init__.py`
```python
from . import models
from . import controller

```

### File: `iot_input_oca/__manifest__.py`
```python

# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "IoT Input",
    "version": "19.0.1.0.0",
    "author": "Creu Blanca, Odoo Community Association (OCA)",
    "category": "IoT",
    "license": "AGPL-3",
    "installable": True,
    "summary": "IoT Input module",
    "depends": ["iot_oca"],
    "website": "https://github.com/OCA/iot",
    "maintainers": ["etobella"],
    "data": [
        "security/ir.model.access.csv",
        "views/iot_device_views.xml",
        "views/iot_device_input_views.xml",
    ],
}

```

### File: `iot_input_oca/models/__init__.py`
```python
from . import iot_device
from . import iot_device_input

```

### File: `iot_input_oca/models/iot_device_input.py`
```python
import logging
import traceback
from io import StringIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class IotDeviceInput(models.Model):
    _name = "iot.device.input"
    _description = "Device input"
    _order = "name"

    name = fields.Char(required=True)
    device_id = fields.Many2one(
        "iot.device", required=True, readonly=True, bypass_search_access=True
    )
    call_model_id = fields.Many2one("ir.model")
    call_function = fields.Char(required=True)
    active = fields.Boolean(default=True)
    serial = fields.Char()
    address = fields.Char()
    passphrase = fields.Char()
    action_ids = fields.One2many(
        "iot.device.input.action",
        inverse_name="input_id",
        readonly=True,
    )
    action_count = fields.Integer(compute="_compute_action_count")
    lang = fields.Selection(
        selection=lambda self: self.env["res.lang"].get_installed(),
        string="Language",
    )

    @api.depends("action_ids")
    def _compute_action_count(self):
        for r in self:
            r.action_count = len(r.action_ids)

    def _call_device(self, *args, **kwargs):
        self.ensure_one()
        obj = self
        if self.call_model_id:
            obj = self.env[self.call_model_id.model].with_context(
                iot_device_input_id=self.id,
                iot_device_name=self.device_id.name,
                iot_device_id=self.device_id.id,
            )
        if self.lang:
            obj = obj.with_context(lang=self.lang)
        return getattr(obj, self.call_function)(*args, **kwargs)

    def parse_args(self, serial, passphrase):
        if not serial or not passphrase:
            raise ValidationError(_("Serial and passphrase are required"))
        return [
            ("serial", "=", serial),
            ("passphrase", "=", passphrase),
            ("device_id.active", "=", True),
        ]

    @api.model
    def get_device(self, serial, passphrase):
        return self.search(self.parse_args(serial, passphrase), limit=1)

    def call_device(self, **kwargs):
        if not self:
            return {"status": "error", "message": _("Device cannot be found")}
        new_kwargs = kwargs.copy()
        args = []
        if "value" in new_kwargs and len(new_kwargs) == 1:
            args.append(new_kwargs.pop("value"))
        try:
            # We want to control that if an error happens,
            # everything will return to normal but we can process it properly
            with self.env.cr.savepoint():
                res = self._call_device(*args, **new_kwargs)
                if not res.get("status"):
                    res["status"] = "ok"
                error = False
        except self._swallable_exceptions():
            buff = StringIO()
            traceback.print_exc(file=buff)
            error = buff.getvalue()
            _logger.error(error)
            res = {"status": "ko"}
        self.device_id.last_contact_date = fields.Datetime.now()
        self.env["iot.device.input.action"].create(
            self._add_action_vals(res, error, args, new_kwargs)
        )
        return res

    def _swallable_exceptions(self):
        # TODO: improve this list
        return (UserError, ValidationError, AttributeError, TypeError)

    def _add_action_vals(self, res, error, args, kwargs):
        new_res = res.copy()
        if error:
            new_res["error"] = error
        return {
            "input_id": self.id,
            "args": str(args or kwargs),
            "res": str(res),
        }

    def test_input_device(self, value):
        return {"value": value}

    def test_model_function(self, value):
        return {"status": "ok", "message": value}

    def parse_multi_input(self, values):
        """Handle multiple inputs for device
        :param list values:
            Values is a list of dicts with at least values for keys 'address', 'value'
            Each dict in the list can have:
             - Different address (multi input)
             - Same address, different values (multi event)
             - Mix of the above (multi input, multi event)
        :returns: JSON encodable list of dicts
        :rtype: list
        """
        device = self.device_id
        if not values:
            _logger.warning(
                "Empty values array for input with identification %s",
                self.serial,
            )
            return {"status": "ko"}
        res = []
        for d in values:
            res.append(device.parse_single_input(**d))
        return {"result": res}


class IoTDeviceAction(models.Model):
    _name = "iot.device.input.action"
    _description = "Action of device inputs"

    input_id = fields.Many2one("iot.device.input")
    args = fields.Char()
    kwargs = fields.Char()
    res = fields.Char()

```

### File: `iot_input_oca/models/iot_device.py`
```python
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class IotDevice(models.Model):
    _inherit = "iot.device"

    input_ids = fields.One2many("iot.device.input", inverse_name="device_id")
    input_count = fields.Integer(compute="_compute_input_count")

    @api.depends("input_ids")
    def _compute_input_count(self):
        for r in self:
            r.input_count = len(r.input_ids)

    def action_show_input(self):
        self.ensure_one()
        action = self.env.ref("iot_input_oca.iot_device_input_action")
        result = action.read()[0]

        result["context"] = {
            "default_device_id": self.id,
        }
        result["domain"] = [("device_id", "=", self.id)]
        if len(self.input_ids) == 1:
            result["views"] = [(False, "form")]
            result["res_id"] = self.input_ids.id
        return result

    def parse_single_input(self, uuid=False, address=False, **kwargs):
        """Handle single input for device

        :param dict value:
            Dict containing at least keys 'address', 'value'
        :returns: dict with keys 'status', 'message' where:
            - status='ok' when value is parsed without errors
            - status='error' and message='error message' when error occurs
            If value contains a value with key 'uuid', it is passed in the return dict
            to identify result for each entry at the iot end
        :rtype: dict
        """
        msg = {}
        if uuid:
            msg["uuid"] = uuid
        if not address:
            _logger.warning("Address for Input is required")
            msg.update(
                {"status": "error", "message": _("Address for Input is required")}
            )
            return msg
        device_input = self.input_ids.filtered(lambda i: i.address == str(address))
        if len(device_input) == 1:
            if not device_input.active:
                _logger.warning(
                    "Input with address %s is inactive, no data will be logged",
                    device_input.address,
                )
                msg.update(
                    {
                        "status": "error",
                        "message": _("Server Error. Check server logs"),
                    }
                )
                return msg
            res = device_input.call_device(**kwargs)
            if uuid:
                res["uuid"] = uuid
            return res
        else:
            _logger.warning("Input with address %s not found", address)
            msg.update(
                {"status": "error", "message": _("Server Error. Check server logs")}
            )
            return msg

```

### File: `iot_input_oca/pyproject.toml`
```toml
[build-system]
requires = ["whool"]
build-backend = "whool.buildapi"

```

### File: `iot_input_oca/security/ir.model.access.csv`
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_iot_device_input,access_iot_device_input,model_iot_device_input,iot_oca.group_iot_user,1,1,1,0
manage_iot_device_input,access_iot_device_input,model_iot_device_input,iot_oca.group_iot_manager,1,1,1,1
access_iot_device_input_action,access_iot_device_input_action,model_iot_device_input_action,iot_oca.group_iot_user,1,1,1,0
manage_iot_device_input_action,access_iot_device_input_action,model_iot_device_input_action,iot_oca.group_iot_manager,1,1,1,1

```

### File: `iot_input_oca/static/description/index.html`
```text
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<meta name="generator" content="Docutils: https://docutils.sourceforge.io/" />
<title>IoT Input</title>
<style type="text/css">

/*
:Author: David Goodger (goodger@python.org)
:Id: $Id: html4css1.css 9511 2024-01-13 09:50:07Z milde $
:Copyright: This stylesheet has been placed in the public domain.

Default cascading style sheet for the HTML output of Docutils.
Despite the name, some widely supported CSS2 features are used.

See https://docutils.sourceforge.io/docs/howto/html-stylesheets.html for how to
customize this style sheet.
*/

/* used to remove borders from tables and images */
.borderless, table.borderless td, table.borderless th {
  border: 0 }

table.borderless td, table.borderless th {
  /* Override padding for "table.docutils td" with "! important".
     The right padding separates the table cells. */
  padding: 0 0.5em 0 0 ! important }

.first {
  /* Override more specific margin styles with "! important". */
  margin-top: 0 ! important }

.last, .with-subtitle {
  margin-bottom: 0 ! important }

.hidden {
  display: none }

.subscript {
  vertical-align: sub;
  font-size: smaller }

.superscript {
  vertical-align: super;
  font-size: smaller }

a.toc-backref {
  text-decoration: none ;
  color: black }

blockquote.epigraph {
  margin: 2em 5em ; }

dl.docutils dd {
  margin-bottom: 0.5em }

object[type="image/svg+xml"], object[type="application/x-shockwave-flash"] {
  overflow: hidden;
}

/* Uncomment (and remove this text!) to get bold-faced definition list terms
dl.docutils dt {
  font-weight: bold }
*/

div.abstract {
  margin: 2em 5em }

div.abstract p.topic-title {
  font-weight: bold ;
  text-align: center }

div.admonition, div.attention, div.caution, div.danger, div.error,
div.hint, div.important, div.note, div.tip, div.warning {
  margin: 2em ;
  border: medium outset ;
  padding: 1em }

div.admonition p.admonition-title, div.hint p.admonition-title,
div.important p.admonition-title, div.note p.admonition-title,
div.tip p.admonition-title {
  font-weight: bold ;
  font-family: sans-serif }

div.attention p.admonition-title, div.caution p.admonition-title,
div.danger p.admonition-title, div.error p.admonition-title,
div.warning p.admonition-title, .code .error {
  color: red ;
  font-weight: bold ;
  font-family: sans-serif }

/* Uncomment (and remove this text!) to get reduced vertical space in
   compound paragraphs.
div.compound .compound-first, div.compound .compound-middle {
  margin-bottom: 0.5em }

div.compound .compound-last, div.compound .compound-middle {
  margin-top: 0.5em }
*/

div.dedication {
  margin: 2em 5em ;
  text-align: center ;
  font-style: italic }

div.dedication p.topic-title {
  font-weight: bold ;
  font-style: normal }

div.figure {
  margin-left: 2em ;
  margin-right: 2em }

div.footer, div.header {
  clear: both;
  font-size: smaller }

div.line-block {
  display: block ;
  margin-top: 1em ;
  margin-bottom: 1em }

div.line-block div.line-block {
  margin-top: 0 ;
  margin-bottom: 0 ;
  margin-left: 1.5em }

div.sidebar {
  margin: 0 0 0.5em 1em ;
  border: medium outset ;
  padding: 1em ;
  background-color: #ffffee ;
  width: 40% ;
  float: right ;
  clear: right }

div.sidebar p.rubric {
  font-family: sans-serif ;
  font-size: medium }

div.system-messages {
  margin: 5em }

div.system-messages h1 {
  color: red }

div.system-message {
  border: medium outset ;
  padding: 1em }

div.system-message p.system-message-title {
  color: red ;
  font-weight: bold }

div.topic {
  margin: 2em }

h1.section-subtitle, h2.section-subtitle, h3.section-subtitle,
h4.section-subtitle, h5.section-subtitle, h6.section-subtitle {
  margin-top: 0.4em }

h1.title {
  text-align: center }

h2.subtitle {
  text-align: center }

hr.docutils {
  width: 75% }

img.align-left, .figure.align-left, object.align-left, table.align-left {
  clear: left ;
  float: left ;
  margin-right: 1em }

img.align-right, .figure.align-right, object.align-right, table.align-right {
  clear: right ;
  float: right ;
  margin-left: 1em }

img.align-center, .figure.align-center, object.align-center {
  display: block;
  margin-left: auto;
  margin-right: auto;
}

table.align-center {
  margin-left: auto;
  margin-right: auto;
}

.align-left {
  text-align: left }

.align-center {
  clear: both ;
  text-align: center }

.align-right {
  text-align: right }

/* reset inner alignment in figures */
div.align-right {
  text-align: inherit }

/* div.align-center * { */
/*   text-align: left } */

.align-top    {
  vertical-align: top }

.align-middle {
  vertical-align: middle }

.align-bottom {
  vertical-align: bottom }

ol.simple, ul.simple {
  margin-bottom: 1em }

ol.arabic {
  list-style: decimal }

ol.loweralpha {
  list-style: lower-alpha }

ol.upperalpha {
  list-style: upper-alpha }

ol.lowerroman {
  list-style: lower-roman }

ol.upperroman {
  list-style: upper-roman }

p.attribution {
  text-align: right ;
  margin-left: 50% }

p.caption {
  font-style: italic }

p.credits {
  font-style: italic ;
  font-size: smaller }

p.label {
  white-space: nowrap }

p.rubric {
  font-weight: bold ;
  font-size: larger ;
  color: maroon ;
  text-align: center }

p.sidebar-title {
  font-family: sans-serif ;
  font-weight: bold ;
  font-size: larger }

p.sidebar-subtitle {
  font-family: sans-serif ;
  font-weight: bold }

p.topic-title {
  font-weight: bold }

pre.address {
  margin-bottom: 0 ;
  margin-top: 0 ;
  font: inherit }

pre.literal-block, pre.doctest-block, pre.math, pre.code {
  margin-left: 2em ;
  margin-right: 2em }

pre.code .ln { color: gray; } /* line numbers */
pre.code, code { background-color: #eeeeee }
pre.code .comment, code .comment { color: #5C6576 }
pre.code .keyword, code .keyword { color: #3B0D06; font-weight: bold }
pre.code .literal.string, code .literal.string { color: #0C5404 }
pre.code .name.builtin, code .name.builtin { color: #352B84 }
pre.code .deleted, code .deleted { background-color: #DEB0A1}
pre.code .inserted, code .inserted { background-color: #A3D289}

span.classifier {
  font-family: sans-serif ;
  font-style: oblique }

span.classifier-delimiter {
  font-family: sans-serif ;
  font-weight: bold }

span.interpreted {
  font-family: sans-serif }

span.option {
  white-space: nowrap }

span.pre {
  white-space: pre }

span.problematic, pre.problematic {
  color: red }

span.section-subtitle {
  /* font-size relative to parent (h1..h6 element) */
  font-size: 80% }

table.citation {
  border-left: solid 1px gray;
  margin-left: 1px }

table.docinfo {
  margin: 2em 4em }

table.docutils {
  margin-top: 0.5em ;
  margin-bottom: 0.5em }

table.footnote {
  border-left: solid 1px black;
  margin-left: 1px }

table.docutils td, table.docutils th,
table.docinfo td, table.docinfo th {
  padding-left: 0.5em ;
  padding-right: 0.5em ;
  vertical-align: top }

table.docutils th.field-name, table.docinfo th.docinfo-name {
  font-weight: bold ;
  text-align: left ;
  white-space: nowrap ;
  padding-left: 0 }

/* "booktabs" style (no vertical lines) */
table.docutils.booktabs {
  border: 0px;
  border-top: 2px solid;
  border-bottom: 2px solid;
  border-collapse: collapse;
}
table.docutils.booktabs * {
  border: 0px;
}
table.docutils.booktabs th {
  border-bottom: thin solid;
  text-align: left;
}

h1 tt.docutils, h2 tt.docutils, h3 tt.docutils,
h4 tt.docutils, h5 tt.docutils, h6 tt.docutils {
  font-size: 100% }

ul.auto-toc {
  list-style-type: none }

</style>
</head>
<body>
<div class="document">


<a class="reference external image-reference" href="https://odoo-community.org/get-involved?utm_source=readme">
<img alt="Odoo Community Association" src="https://odoo-community.org/readme-banner-image" />
</a>
<div class="section" id="iot-input">
<h1>IoT Input</h1>
<!-- !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! This file is generated by oca-gen-addon-readme !!
!! changes will be overwritten.                   !!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! source digest: sha256:712a7f4515d804c522f60180687a68c12af9368ed547a48debfc6d67197e3e5a
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! -->
<p><a class="reference external image-reference" href="https://odoo-community.org/page/development-status"><img alt="Beta" src="https://img.shields.io/badge/maturity-Beta-yellow.png" /></a> <a class="reference external image-reference" href="http://www.gnu.org/licenses/agpl-3.0-standalone.html"><img alt="License: AGPL-3" src="https://img.shields.io/badge/license-AGPL--3-blue.png" /></a> <a class="reference external image-reference" href="https://github.com/OCA/iot/tree/18.0/iot_input_oca"><img alt="OCA/iot" src="https://img.shields.io/badge/github-OCA%2Fiot-lightgray.png?logo=github" /></a> <a class="reference external image-reference" href="https://translation.odoo-community.org/projects/iot-18-0/iot-18-0-iot_input_oca"><img alt="Translate me on Weblate" src="https://img.shields.io/badge/weblate-Translate%20me-F47D42.png" /></a> <a class="reference external image-reference" href="https://runboat.odoo-community.org/builds?repo=OCA/iot&amp;target_branch=18.0"><img alt="Try me on Runboat" src="https://img.shields.io/badge/runboat-Try%20me-875A7B.png" /></a></p>
<p>This addon allows to use a device in order to input data to odoo
automatically.</p>
<p>It opens a URL that a device can use to connect (with a password) that
can only execute an specific action.</p>
<p>Inputs are useful when a device wants to communicate to odoo for a
single and simple action. This way, the device does not need to be
configured with a odoo user and password, it is handled by odoo devices.</p>
<p>Examples:</p>
<ul class="simple">
<li>Sending the temperature every three minutes.</li>
<li>Sending the RFID that the device has received in order to perform some
action</li>
</ul>
<p><strong>Table of contents</strong></p>
<div class="contents local topic" id="contents">
<ul class="simple">
<li><a class="reference internal" href="#usage" id="toc-entry-1">Usage</a></li>
<li><a class="reference internal" href="#bug-tracker" id="toc-entry-2">Bug Tracker</a></li>
<li><a class="reference internal" href="#credits" id="toc-entry-3">Credits</a><ul>
<li><a class="reference internal" href="#authors" id="toc-entry-4">Authors</a></li>
<li><a class="reference internal" href="#contributors" id="toc-entry-5">Contributors</a></li>
<li><a class="reference internal" href="#maintainers" id="toc-entry-6">Maintainers</a></li>
</ul>
</li>
</ul>
</div>
<div class="section" id="usage">
<h2><a class="toc-backref" href="#toc-entry-1">Usage</a></h2>
<p>There are two endpoints you can use: Endpoint 1: /iot/&lt;serial&gt;/action</p>
<p>Takes application/x-www-form-urlencoded parameters: passphase, value
(where value is a JSON object)</p>
<ol class="arabic simple">
<li>Create a Device on IoT &gt; Config Devices</li>
<li>Access the Inputs section of the device</li>
<li>Create an input. You must define a serial, passphrase, function and
model</li>
</ol>
<p>The function that the system will call must be of the following kind:</p>
<pre class="literal-block">
&#64;api.model
    def call_function(self, key):
    return {}
</pre>
<p>Where key is the input string send by the device and the result must be
a dictionary that will be responded to the device as a JSON.</p>
<p>Endpoint 2: /iot/&lt;device_identification&gt;/multi_input It can be used to
send values with multiple data in one POST request such as: - Values for
inputs of the same device with different address (multi input) - Values
for inputs of the same device with same address, different values (multi
event) - Mix of the above (multi input, multi event)</p>
<p>Takes application/x-www-form-urlencoded parameters: passphase, values (a
JSON array of JSON objects)</p>
<p>It is called using device_identification and passing two POST
parameters: device passphrase and a JSON string containing an array of
values for input - The value for the address key can be a string or a
numeric (to conserve bytes in memory restricted devices when creating
the JSON object) and is converted to string when parsing. - The value
for the value key can either be string, number or boolean according to
JSON specs. You can see an example of a valid JSON input object in the
examples folder, using a few combinations.</p>
<p>It requires the function that the system will call must be of the
following kind:</p>
<pre class="literal-block">
&#64;api.model
    def call_function(self, key):
    'do something
    if err:
        return {'status': 'error', 'message': 'The error message you want to send to the device'}
    return {'status': 'ok', 'message': 'Optional success message'}
</pre>
<p>Where key is a dict send by the device having at least value for keys:
‘address’, ‘value’</p>
<p>The function must always return a JSON with status and message. If value
contains a value with ‘uuid’ as key, it is returned along with the
object for the IoT device to identify success/failure per record.</p>
<p>It has full error reporting and the return value is a JSON array of
dicts containing at least status and message. Error message respose is
at some points generic, though extended logging is done in Odoo server
logs.</p>
</div>
<div class="section" id="bug-tracker">
<h2><a class="toc-backref" href="#toc-entry-2">Bug Tracker</a></h2>
<p>Bugs are tracked on <a class="reference external" href="https://github.com/OCA/iot/issues">GitHub Issues</a>.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
<a class="reference external" href="https://github.com/OCA/iot/issues/new?body=module:%20iot_input_oca%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**">feedback</a>.</p>
<p>Do not contact contributors directly about support or help with technical issues.</p>
</div>
<div class="section" id="credits">
<h2><a class="toc-backref" href="#toc-entry-3">Credits</a></h2>
<div class="section" id="authors">
<h3><a class="toc-backref" href="#toc-entry-4">Authors</a></h3>
<ul class="simple">
<li>Creu Blanca</li>
</ul>
</div>
<div class="section" id="contributors">
<h3><a class="toc-backref" href="#toc-entry-5">Contributors</a></h3>
<ul class="simple">
<li>Enric Tobella &lt;<a class="reference external" href="mailto:etobella&#64;creublanca.es">etobella&#64;creublanca.es</a>&gt;</li>
<li>Dimitrios Tanis &lt;<a class="reference external" href="mailto:dtanis&#64;tanisfood.gr">dtanis&#64;tanisfood.gr</a>&gt;</li>
</ul>
</div>
<div class="section" id="maintainers">
<h3><a class="toc-backref" href="#toc-entry-6">Maintainers</a></h3>
<p>This module is maintained by the OCA.</p>
<a class="reference external image-reference" href="https://odoo-community.org">
<img alt="Odoo Community Association" src="https://odoo-community.org/logo.png" />
</a>
<p>OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.</p>
<p>Current <a class="reference external" href="https://odoo-community.org/page/maintainer-role">maintainer</a>:</p>
<p><a class="reference external image-reference" href="https://github.com/etobella"><img alt="etobella" src="https://github.com/etobella.png?size=40px" /></a></p>
<p>This module is part of the <a class="reference external" href="https://github.com/OCA/iot/tree/18.0/iot_input_oca">OCA/iot</a> project on GitHub.</p>
<p>You are welcome to contribute. To learn how please visit <a class="reference external" href="https://odoo-community.org/page/Contribute">https://odoo-community.org/page/Contribute</a>.</p>
</div>
</div>
</div>
</div>
</body>
</html>

```

### File: `iot_input_oca/tests/__init__.py`
```python
from . import test_iot_in
from . import test_iot_multi_input
from . import test_iot_controller

```

### File: `iot_input_oca/tests/models.py`
```python
from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def test_fake_iot_input(self, value):
        partner = self.browse(value)
        partner.message_post(body=str(value))
        return {}

```

### File: `iot_input_oca/tests/test_iot_controller.py`
```python
import json

from odoo.tests.common import HttpCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestIotController(HttpCase):
    readonly_enabled = False

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))
        self.device_identification = "test_device_name"
        self.passphrase = "password"
        self.system = self.env["iot.communication.system"].create(
            {"name": "Demo system"}
        )
        self.device = self.env["iot.device"].create(
            {
                "name": "Device",
                "communication_system_id": self.system.id,
            }
        )
        self.address_1 = "I0"
        self.serial = "testingdeviceserial"
        self.input_passphrase = "password"
        self.device_input_1 = self.env["iot.device.input"].create(
            {
                "name": "Input 1",
                "device_id": self.device.id,
                "address": self.address_1,
                "serial": self.serial,
                "passphrase": self.input_passphrase,
                "call_model_id": self.env.ref(
                    "iot_input_oca.model_iot_device_input"
                ).id,
                "call_function": "test_model_function",
            }
        )
        self.address_2 = "I1"
        self.env["iot.device.input"].create(
            {
                "name": "Input 2",
                "device_id": self.device.id,
                "address": self.address_2,
                "call_model_id": self.env.ref(
                    "iot_input_oca.model_iot_device_input"
                ).id,
                "call_function": "test_model_function",
            }
        )
        self.env["iot.device.input"].create(
            {
                "name": "Multi Input",
                "device_id": self.device.id,
                "serial": self.device_identification,
                "passphrase": self.passphrase,
                "call_function": "parse_multi_input",
            }
        )
        self.single_input_values = [{"input": self.address_1, "value": "test"}]
        self.values = json.dumps(
            [
                {"address": self.address_1, "value": "test value 1"},
                {
                    "address": self.address_1,
                    "value": 2.3,
                },  # Checking that nothing wrong happens with a non string
                {"address": self.address_2, "value": "test value 3"},
            ]
        )

    def test_single_controller(self):
        res = self.url_open(
            f"/iot/{self.serial}/action",
            data={"passphrase": self.input_passphrase, "value": "123"},
        )
        self.assertEqual(res.json()["status"], "ok")

    def test_single_controller_archived_device(self):
        self.device.write({"active": False})
        res = self.url_open(
            f"/iot/{self.serial}/action",
            data={"passphrase": self.input_passphrase, "value": "123"},
        )
        self.assertEqual(res.json()["status"], "error")

    def test_multi_controller_archived_device(self):
        self.device.write({"active": False})
        res = self.url_open(
            f"/iot/{self.serial}/multi_input",
            data={"passphrase": self.input_passphrase, "values": self.values},
        )
        self.assertEqual(res.json()["status"], "error")

    @mute_logger("odoo.addons.iot_input_oca.controller.iot_input_controller")
    def test_multi_input_controller_error_passphrase(self):
        res = self.url_open(
            f"/iot/{self.device_identification}/multi_input",
            data={"values": self.values},
        ).json()
        self.assertEqual(res["status"], "error")

    @mute_logger("odoo.addons.iot_input_oca.controller.iot_input_controller")
    def test_multi_input_controller_error_values(self):
        res = self.url_open(
            f"/iot/{self.device_identification}/multi_input",
            data={"passphrase": self.passphrase},
        ).json()
        self.assertEqual(res["status"], "error")

    @mute_logger("odoo.addons.iot_input_oca.controller.iot_input_controller")
    def test_multi_input_controller_syntax_error(self):
        res = self.url_open(
            f"/iot/{self.device_identification}/multi_input",
            data={"passphrase": self.passphrase, "values": "{}"},
        ).json()
        self.assertEqual(res["status"], "error")

    @mute_logger("odoo.addons.iot_input_oca.controller.iot_input_controller")
    def test_multi_input_controller_malformed_error(self):
        res = self.url_open(
            f"/iot/{self.device_identification}/multi_input",
            data={"passphrase": self.passphrase, "values": "{1234}"},
        ).json()
        self.assertEqual(res["status"], "error")

    def test_multi_input_controller(self):
        res = self.url_open(
            f"/iot/{self.device_identification}/multi_input",
            data={"passphrase": self.passphrase, "values": self.values},
        )
        result = res.json()
        for response in result:
            self.assertEqual(response["status"], "ok")

    def test_multi_input_controller_unauthorized_iot_exists(self):
        res = self.url_open(
            f"/iot/{self.serial}/check", data={"passphrase": self.input_passphrase}
        ).json()
        self.assertEqual(res["state"], True)

    def test_multi_input_controller_unauthorized_iot_no_exists(self):
        res = self.url_open(
            f"/iot/{self.passphrase}/check",
            data={"passphrase": self.input_passphrase},
        ).json()
        self.assertEqual(res["state"], False)

```

### File: `iot_input_oca/tests/test_iot_in.py`
```python
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestIotIn(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.serial = "testingdeviceserial"
        cls.passphrase = "password"
        cls.system = cls.env["iot.communication.system"].create({"name": "Demo system"})
        cls.device = cls.env["iot.device"].create(
            {"name": "Device", "communication_system_id": cls.system.id}
        )
        cls.device_input = cls.env["iot.device.input"].create(
            {
                "name": "Input",
                "device_id": cls.device.id,
                "active": True,
                "serial": cls.serial,
                "passphrase": cls.passphrase,
                "call_model_id": cls.env.ref("iot_input_oca.model_iot_device_input").id,
                "call_function": "test_input_device",
            }
        )
        cls.iot = cls.env["iot.device.input"]

    def test_device_action_count_ids(self):
        self.assertEqual(self.device.input_count, 1)

    def _get_devices(self):
        action = self.device.action_show_input()
        devices = self.env[action["res_model"]]
        if action["res_id"]:
            devices = devices.browse(action["res_id"])
        else:
            devices = devices.search(action["domain"])
        return devices

    def test_device_action(self):
        devices = self._get_devices()
        self.assertEqual(devices, self.device_input)
        device_input_02 = self.env["iot.device.input"].create(
            {
                "name": "Input",
                "device_id": self.device.id,
                "active": True,
                "serial": self.serial + self.serial,
                "passphrase": self.passphrase,
                "call_model_id": self.env.ref(
                    "iot_input_oca.model_iot_device_input"
                ).id,
                "call_function": "test_input_device",
            }
        )
        devices = self._get_devices()
        self.assertIn(self.device_input, devices)
        self.assertIn(device_input_02, devices)

    def test_device_error_wrong_serial(self):
        self.assertFalse(
            self.iot.get_device(
                serial=self.serial + self.serial, passphrase=self.passphrase
            )
        )

    def test_device_error_wrong_passphrase(self):
        self.assertFalse(
            self.iot.get_device(
                serial=self.serial, passphrase=self.passphrase + self.passphrase
            )
        )

    def test_device_error_archived(self):
        self.device_input.active = False
        self.assertFalse(
            self.iot.get_device(serial=self.serial, passphrase=self.passphrase)
        )

    def test_device_error_missing_data(self):
        with self.assertRaises(ValidationError):
            self.iot.get_device(serial=False, passphrase=self.passphrase)

    def test_error_execution_without_device(self):
        res = self.iot.call_device(value="hello")
        self.assertEqual(res["status"], "error")

    def test_device_input_calling(self):
        iot = self.iot.get_device(serial=self.serial, passphrase=self.passphrase)
        self.assertEqual(iot, self.device_input)
        self.assertEqual(0, self.device_input.action_count)
        args = "hello"
        res = iot.call_device(value=args)
        self.assertEqual(res, {"status": "ok", "value": args})
        self.assertTrue(self.device_input.action_ids)
        self.assertEqual(self.device_input.action_ids.args, str([args]))
        self.assertEqual(self.device_input.action_ids.res, str(res))
        self.assertEqual(1, self.device_input.action_count)

    def test_device_input_calling_with_lang(self):
        devices = self._get_devices()
        self.assertEqual(devices, self.device_input)
        device_input_lang = self.env["iot.device.input"].create(
            {
                "name": "Input",
                "lang": "en_US",
                "device_id": self.device.id,
                "active": True,
                "serial": self.serial + self.serial,
                "passphrase": self.passphrase,
                "call_model_id": self.env.ref(
                    "iot_input_oca.model_iot_device_input"
                ).id,
                "call_function": "test_input_device",
            }
        )
        devices = self._get_devices()
        self.assertIn(self.device_input, devices)
        self.assertIn(device_input_lang, devices)
        args = "hello"
        res = device_input_lang.call_device(value=args)
        self.assertEqual(res, {"status": "ok", "value": args})

```

### File: `iot_input_oca/tests/test_iot_multi_input.py`
```python
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestIotIn(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.device_identification = "test_device_name"
        cls.passphrase = "password"

        cls.system = cls.env["iot.communication.system"].create({"name": "Demo system"})
        cls.device = cls.env["iot.device"].create(
            {
                "name": "Device",
                "communication_system_id": cls.system.id,
            }
        )
        cls.address_1 = "I0"
        cls.device_input_1 = cls.env["iot.device.input"].create(
            {
                "name": "Input 1",
                "device_id": cls.device.id,
                "address": cls.address_1,
                "call_model_id": cls.env.ref("iot_input_oca.model_iot_device_input").id,
                "call_function": "test_model_function",
            }
        )
        cls.address_2 = "I1"
        cls.env["iot.device.input"].create(
            {
                "name": "Input 2",
                "device_id": cls.device.id,
                "address": cls.address_2,
                "call_model_id": cls.env.ref("iot_input_oca.model_iot_device_input").id,
                "call_function": "test_model_function",
            }
        )
        cls.env["iot.device.input"].create(
            {
                "name": "Multi Input",
                "device_id": cls.device.id,
                "serial": cls.device_identification,
                "passphrase": cls.passphrase,
                "call_function": "parse_multi_input",
            }
        )
        cls.single_input_values = [{"input": cls.address_1, "value": "test"}]
        cls.iot = cls.env["iot.device.input"]

    def test_multi_input_error_wrong_identification(self):
        iot = self.iot.get_device(
            serial=self.device_identification + self.device_identification,
            passphrase=self.passphrase,
        )
        # device not found -> result is error
        self.assertEqual(
            iot.call_device(values=self.single_input_values)["status"],
            "error",
        )

    @mute_logger("odoo.addons.iot_input_oca.models.iot_device_input")
    def test_multi_input_error_no_inputs(self):
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        self.assertEqual(
            iot.call_device(values=[])["status"],
            "ko",
        )

    @mute_logger("odoo.addons.iot_input_oca.models.iot_device")
    def test_multi_input_non_existing_address(self):
        non_existing_address = "I3"
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        for response in iot.call_device(
            values=[{"address": non_existing_address, "value": "test value 1"}],
        )["result"]:
            self.assertEqual(response["status"], "error")

    @mute_logger("odoo.addons.iot_input_oca.models.iot_device_input")
    def test_error_missing_parameter(self):
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        for response in iot.call_device(values=[{"address": self.address_1}])["result"]:
            self.assertEqual(response["status"], "ko")

    @mute_logger("odoo.addons.iot_input_oca.models.iot_device_input")
    def test_error_with_extra_args(self):
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        for response in iot.call_device(
            values=[{"address": self.address_1, "uuid": "abc"}],
        )["result"]:
            self.assertEqual(response["status"], "ko")
            self.assertTrue("uuid" in response)

    @mute_logger("odoo.addons.iot_input_oca.models.iot_device")
    def test_error_no_address_with_extra_args(self):
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        for response in iot.call_device(values=[{"uuid": "abc"}])["result"]:
            self.assertEqual(response["status"], "error")
            self.assertTrue("uuid" in response)

    @mute_logger("odoo.addons.iot_input_oca.models.iot_device")
    def test_error_no_address(self):
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        for response in iot.call_device(values=[{"value": "test value"}])["result"]:
            self.assertEqual(response["status"], "error")

    def test_correct_one_input(self):
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        for response in iot.call_device(
            values=[{"address": self.address_1, "value": "test"}],
        )["result"]:
            self.assertEqual(response["status"], "ok")

    def test_correct_two_inputs(self):
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        for response in iot.call_device(
            values=[
                {"address": self.address_1, "value": "test value 1"},
                {
                    "address": self.address_1,
                    "value": 2.3,
                },  # Checking that nothing wrong happens with a non string
                {"address": self.address_2, "value": "test value 3"},
            ],
        )["result"]:
            self.assertEqual(response["status"], "ok")

    def test_correct_with_extra_args(self):
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        response_with_uuid = [
            {"address": self.address_1, "value": "test value 1", "uuid": "abc"},
            {"address": self.address_1, "value": "test value 2", "uuid": "def"},
            {"address": self.address_2, "value": "test value 3", "uuid": "ghi"},
        ]
        for response in iot.call_device(values=response_with_uuid)["result"]:
            self.assertTrue(response["uuid"])
            self.assertEqual(
                response["message"],
                [x for x in response_with_uuid if x["uuid"] == response["uuid"]][0][
                    "value"
                ],
            )

    def test_error_archived_device(self):
        self.device.active = False
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        self.assertEqual(
            iot.call_device(
                values=[{"address": self.address_1, "value": "test"}],
            )["status"],
            "error",
        )

    @mute_logger("odoo.addons.iot_input_oca.models.iot_device")
    def test_error_archived_device_input(self):
        self.device_input_1.active = False
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        for result in iot.call_device(
            values=[{"address": self.address_1, "value": "test"}],
        )["result"]:
            self.assertEqual(
                result["status"],
                "error",
            )

    @mute_logger("odoo.addons.iot_input_oca.models.iot_device")
    def test_error_archived_device_input_extra_args(self):
        self.device_input_1.active = False
        iot = self.iot.get_device(
            serial=self.device_identification, passphrase=self.passphrase
        )
        for result in iot.call_device(
            values=[{"address": self.address_1, "value": "test", "uuid": "ghi"}],
        )["result"]:
            self.assertEqual(
                result["status"],
                "error",
            )
            self.assertEqual(result["uuid"], "ghi")

```

### File: `iot_input_oca/views/iot_device_input_views.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <record id="iot_device_input_list" model="ir.ui.view">
        <field name="name">iot.device.input.list</field>
        <field name="model">iot.device.input</field>
        <field name="arch" type="xml">
            <list delete="0">
                <field name="name" />
                <field name="address" />
                <field name="serial" />
            </list>
        </field>
    </record>
    <record id="iot_device_input_form" model="ir.ui.view">
        <field name="name">iot.device.input.form</field>
        <field name="model">iot.device.input</field>
        <field name="arch" type="xml">
            <form>
                <header />
                <sheet>
                    <widget
                        name="web_ribbon"
                        text="Archived"
                        bg_color="bg-danger"
                        invisible="active"
                    />
                    <field name="active" invisible="1" />
                    <div class="oe_button_box" name="button_box" />
                    <div class="oe_title">
                        <h1>
                            <field name="name" />
                        </h1>
                    </div>
                    <group>
                        <group>
                            <field name="address" />
                            <field name="serial" />
                            <field name="passphrase" widget="password" />
                        </group>
                        <group>
                            <field name="call_model_id" options="{'no_create':True}" />
                            <field name="call_function" />
                            <field name="lang" />
                        </group>
                    </group>
                    <notebook invisible="1" />
                </sheet>
            </form>
        </field>
    </record>
    <record id="iot_device_input_search" model="ir.ui.view">
        <field name="name">iot.device.input.search</field>
        <field name="model">iot.device.input</field>
        <field name="arch" type="xml">
            <search string="IoT Device Input Search">
                <field name="name" />
                <filter
                    name="active"
                    string="Active"
                    domain="[('active','=',True)]"
                    help="Active"
                />
                <filter
                    name="inactive"
                    string="Inactive"
                    domain="[('active','=',False)]"
                    help="Inactive"
                />
                <separator />
            </search>
        </field>
    </record>
    <record model="ir.actions.act_window" id="iot_device_input_action">
        <field name="name">IoT Inputs</field>
        <field name="type">ir.actions.act_window</field>
        <field name="res_model">iot.device.input</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>

```

### File: `iot_input_oca/views/iot_device_views.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <record id="iot_device_form" model="ir.ui.view">
        <field name="name">iot.device.form</field>
        <field name="model">iot.device</field>
        <field name="inherit_id" ref="iot_oca.iot_device_form" />
        <field name="arch" type="xml">
            <xpath expr="//div[@name='button_box']" position="inside">
                <button
                    name="action_show_input"
                    type="object"
                    class="oe_stat_button"
                    icon="fa-keyboard-o"
                >
                    <field string="Inputs" name="input_count" widget="statinfo" />
                </button>
            </xpath>
        </field>
    </record>
    <record id="iot_device_kanban" model="ir.ui.view">
        <field name="name">iot.device.kanban</field>
        <field name="model">iot.device</field>
        <field name="inherit_id" ref="iot_oca.iot_device_kanban" />
        <field name="arch" type="xml">
            <xpath expr="//div[@role='menu']/*[1]" position="before">
                <a
                    type="object"
                    name="action_show_input"
                    role="menuitem"
                    class="dropdown-item"
                >
                    <i class="fa fa-keyboard-o" />
                    Inputs
                </a>
            </xpath>
        </field>
    </record>
</odoo>

```

### File: `iot_oca/__init__.py`
```python
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from . import models

```

### File: `iot_oca/__manifest__.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "IoT Base",
    "version": "19.0.1.0.0",
    "category": "IoT",
    "author": "Creu Blanca, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "installable": True,
    "application": True,
    "summary": "IoT base module",
    "website": "https://github.com/OCA/iot",
    "depends": ["base"],
    "data": [
        "security/iot_security.xml",
        "security/ir.model.access.csv",
        "views/iot_menu.xml",
        "views/iot_device_tag.xml",
        "views/iot_device_group.xml",
        "views/iot_system_views.xml",
        "views/iot_device_views.xml",
    ],
}

```

### File: `iot_oca/models/__init__.py`
```python
from . import iot_device
from . import iot_device_action
from . import iot_communication_system
from . import iot_communication_system_action
from . import iot_device_group
from . import iot_device_tag

```

### File: `iot_oca/models/iot_communication_system_action.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging
import traceback
from io import StringIO

from odoo import fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class IoTSystemAction(models.Model):
    _name = "iot.communication.system.action"
    _description = "IoT Communication System action"

    name = fields.Char(required=True)
    communication_system_id = fields.Many2one("iot.communication.system", required=True)

    def _run(self, device_action):
        raise ValidationError(self.env._("Action cannot be processed"))

    def run(self, device_action):
        try:
            result = self._run(device_action)
            return "ok", result
        except Exception:
            buff = StringIO()
            traceback.print_exc(file=buff)
            error = buff.getvalue()
            _logger.warning(error)
            return "failed", error

```

### File: `iot_oca/models/iot_communication_system.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class IoTCommunicationSystem(models.Model):
    _name = "iot.communication.system"
    _description = "IoT Communication System"
    # TODO: Rename it to iot.communication.system System is confusing

    name = fields.Char(required=True)
    device_ids = fields.One2many("iot.device", inverse_name="communication_system_id")
    communication_system_action_ids = fields.One2many(
        "iot.communication.system.action", inverse_name="communication_system_id"
    )

```

### File: `iot_oca/models/iot_device_action.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IoTDeviceAction(models.Model):
    _name = "iot.device.action"
    _description = "IoT Action"
    _order = "date_ok desc"

    device_id = fields.Many2one("iot.device", required=True, readonly=True)
    communication_system_action_id = fields.Many2one(
        "iot.communication.system.action", required=True
    )
    status = fields.Selection(
        [("ok", "Ok"), ("pending", "Pending"), ("failed", "Failed")],
        required=True,
        default="pending",
    )
    result = fields.Text()
    date_ok = fields.Datetime(readonly=True, string="Ok date")

    @api.constrains("device_id", "communication_system_action_id")
    def _check_system(self):
        if self.filtered(
            lambda r: r.device_id.communication_system_id
            != r.communication_system_action_id.communication_system_id
        ):
            raise ValidationError(
                self.env._("Device and action must be of the same system")
            )

    def run_extra_actions(self, status, result):
        return

    def run(self):
        self.ensure_one()
        if self.status != "ok":
            status, result = self.communication_system_action_id.run(self)
            self.write(
                {
                    "status": status,
                    "result": result,
                    "date_ok": fields.Datetime.now() if status == "ok" else False,
                }
            )
            self.run_extra_actions(status, result)

```

### File: `iot_oca/models/iot_device_group.py`
```python
# Copyright 2021 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class IotDeviceGroup(models.Model):
    _name = "iot.device.group"
    _description = "Iot Group"

    name = fields.Char(required=True)

```

### File: `iot_oca/models/iot_device.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class IoTDevice(models.Model):
    _name = "iot.device"
    _description = "IoT Device"
    _inherit = "image.mixin"

    name = fields.Char(required=True)
    communication_system_id = fields.Many2one("iot.communication.system", required=True)
    action_ids = fields.One2many("iot.device.action", inverse_name="device_id")
    active = fields.Boolean(default=True)
    state = fields.Selection([], readonly=True)
    model = fields.Char()
    ip = fields.Char(string="IP")
    action_count = fields.Integer(compute="_compute_action_count")
    group_id = fields.Many2one("iot.device.group")
    tag_ids = fields.Many2many("iot.device.tag")
    color = fields.Integer()
    last_contact_date = fields.Datetime(readonly=True)
    icon = fields.Selection(
        [
            ("fa fa-television fa-4x", "television"),
            ("fa fa-wifi fa-4x", "wifi"),
            ("fa fa-laptop fa-4x", "laptop"),
            ("fa fa-desktop fa-4x", "desktop"),
            ("fa fa-archive fa-4x", "archive"),
            ("fa fa-mobile fa-6x", "mobile"),
        ]
    )

    @api.depends("action_ids")
    def _compute_action_count(self):
        for record in self:
            record.action_count = len(record.action_ids)

    def device_run_action(self):
        system_action = self.env["iot.communication.system.action"].browse(
            self.env.context.get("iot_communication_system_action_id")
        )
        for rec in self:
            action = self.env["iot.device.action"].create(
                {
                    "device_id": rec.id,
                    "communication_system_action_id": system_action.id,
                }
            )
            action.run()

```

### File: `iot_oca/models/iot_device_tag.py`
```python
# Copyright 2021 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class IotDeviceTag(models.Model):
    _name = "iot.device.tag"
    _description = "Device Tag"

    name = fields.Char(required=True)
    color = fields.Integer(string="Color Index")

```

### File: `iot_oca/pyproject.toml`
```toml
[build-system]
requires = ["whool"]
build-backend = "whool.buildapi"

```

### File: `iot_oca/security/iot_security.xml`
```xml
<?xml version="1.0" encoding="utf-8" ?>
<!--
    Copyright 2017 Eficent Business and IT Consulting Services, S.L.
    Copyright 2017 Creu Blanca
    License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
-->
<odoo>
    <record id="ir_module_category_iot" model="ir.module.category">
        <field name="name">IoT</field>
    </record>
    <record id="res_groups_privilege_iot" model="res.groups.privilege">
        <field name="name">IoT</field>
        <field name="category_id" ref="ir_module_category_iot" />
    </record>
    <record id="group_iot_user" model="res.groups">
        <field name="name">IoT User</field>
        <field name="comment">Module user.</field>
        <field name="privilege_id" ref="res_groups_privilege_iot" />
    </record>
    <record id="group_iot_manager" model="res.groups">
        <field name="name">Manager</field>
        <field
            name="comment"
        >Module administrator, able to modify configuration data.</field>
        <field name="privilege_id" ref="res_groups_privilege_iot" />
        <field name="implied_ids" eval="[(4, ref('group_iot_user'))]" />
        <field
            name="user_ids"
            eval="[(4,ref('base.user_root')), (4,ref('base.user_admin'))]"
        />
    </record>
</odoo>

```

### File: `iot_oca/security/ir.model.access.csv`
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_iot_device,access_iot_device,model_iot_device,group_iot_user,1,1,0,0
manage_iot_device,access_iot_device,model_iot_device,group_iot_manager,1,1,1,0
access_iot_device_action,access_iot_device_action,model_iot_device_action,group_iot_user,1,1,1,0
manage_iot_device_action,access_iot_device_action,model_iot_device_action,group_iot_manager,1,1,1,0
access_iot_system,access_iot_system,model_iot_communication_system,group_iot_user,1,0,0,0
manage_iot_system,access_iot_system,model_iot_communication_system,group_iot_manager,1,1,1,0
access_iot_system_action,access_iot_system_action,model_iot_communication_system_action,group_iot_user,1,0,0,0
manage_iot_system_action,access_iot_system_action,model_iot_communication_system_action,group_iot_manager,1,1,1,0
access_iot_device_group,access_iot_device_group,model_iot_device_group,group_iot_user,1,0,0,0
manage_iot_device_group,manage_iot_device_group,model_iot_device_group,group_iot_manager,1,1,1,0
access_iot_device_tag,access_iot_device_tag,model_iot_device_tag,group_iot_user,1,0,0,0
manage_iot_device_tag,manage_iot_device_tag,model_iot_device_tag,group_iot_manager,1,1,1,0

```

### File: `iot_oca/static/description/index.html`
```text
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<meta name="generator" content="Docutils: https://docutils.sourceforge.io/" />
<title>README.rst</title>
<style type="text/css">

/*
:Author: David Goodger (goodger@python.org)
:Id: $Id: html4css1.css 9511 2024-01-13 09:50:07Z milde $
:Copyright: This stylesheet has been placed in the public domain.

Default cascading style sheet for the HTML output of Docutils.
Despite the name, some widely supported CSS2 features are used.

See https://docutils.sourceforge.io/docs/howto/html-stylesheets.html for how to
customize this style sheet.
*/

/* used to remove borders from tables and images */
.borderless, table.borderless td, table.borderless th {
  border: 0 }

table.borderless td, table.borderless th {
  /* Override padding for "table.docutils td" with "! important".
     The right padding separates the table cells. */
  padding: 0 0.5em 0 0 ! important }

.first {
  /* Override more specific margin styles with "! important". */
  margin-top: 0 ! important }

.last, .with-subtitle {
  margin-bottom: 0 ! important }

.hidden {
  display: none }

.subscript {
  vertical-align: sub;
  font-size: smaller }

.superscript {
  vertical-align: super;
  font-size: smaller }

a.toc-backref {
  text-decoration: none ;
  color: black }

blockquote.epigraph {
  margin: 2em 5em ; }

dl.docutils dd {
  margin-bottom: 0.5em }

object[type="image/svg+xml"], object[type="application/x-shockwave-flash"] {
  overflow: hidden;
}

/* Uncomment (and remove this text!) to get bold-faced definition list terms
dl.docutils dt {
  font-weight: bold }
*/

div.abstract {
  margin: 2em 5em }

div.abstract p.topic-title {
  font-weight: bold ;
  text-align: center }

div.admonition, div.attention, div.caution, div.danger, div.error,
div.hint, div.important, div.note, div.tip, div.warning {
  margin: 2em ;
  border: medium outset ;
  padding: 1em }

div.admonition p.admonition-title, div.hint p.admonition-title,
div.important p.admonition-title, div.note p.admonition-title,
div.tip p.admonition-title {
  font-weight: bold ;
  font-family: sans-serif }

div.attention p.admonition-title, div.caution p.admonition-title,
div.danger p.admonition-title, div.error p.admonition-title,
div.warning p.admonition-title, .code .error {
  color: red ;
  font-weight: bold ;
  font-family: sans-serif }

/* Uncomment (and remove this text!) to get reduced vertical space in
   compound paragraphs.
div.compound .compound-first, div.compound .compound-middle {
  margin-bottom: 0.5em }

div.compound .compound-last, div.compound .compound-middle {
  margin-top: 0.5em }
*/

div.dedication {
  margin: 2em 5em ;
  text-align: center ;
  font-style: italic }

div.dedication p.topic-title {
  font-weight: bold ;
  font-style: normal }

div.figure {
  margin-left: 2em ;
  margin-right: 2em }

div.footer, div.header {
  clear: both;
  font-size: smaller }

div.line-block {
  display: block ;
  margin-top: 1em ;
  margin-bottom: 1em }

div.line-block div.line-block {
  margin-top: 0 ;
  margin-bottom: 0 ;
  margin-left: 1.5em }

div.sidebar {
  margin: 0 0 0.5em 1em ;
  border: medium outset ;
  padding: 1em ;
  background-color: #ffffee ;
  width: 40% ;
  float: right ;
  clear: right }

div.sidebar p.rubric {
  font-family: sans-serif ;
  font-size: medium }

div.system-messages {
  margin: 5em }

div.system-messages h1 {
  color: red }

div.system-message {
  border: medium outset ;
  padding: 1em }

div.system-message p.system-message-title {
  color: red ;
  font-weight: bold }

div.topic {
  margin: 2em }

h1.section-subtitle, h2.section-subtitle, h3.section-subtitle,
h4.section-subtitle, h5.section-subtitle, h6.section-subtitle {
  margin-top: 0.4em }

h1.title {
  text-align: center }

h2.subtitle {
  text-align: center }

hr.docutils {
  width: 75% }

img.align-left, .figure.align-left, object.align-left, table.align-left {
  clear: left ;
  float: left ;
  margin-right: 1em }

img.align-right, .figure.align-right, object.align-right, table.align-right {
  clear: right ;
  float: right ;
  margin-left: 1em }

img.align-center, .figure.align-center, object.align-center {
  display: block;
  margin-left: auto;
  margin-right: auto;
}

table.align-center {
  margin-left: auto;
  margin-right: auto;
}

.align-left {
  text-align: left }

.align-center {
  clear: both ;
  text-align: center }

.align-right {
  text-align: right }

/* reset inner alignment in figures */
div.align-right {
  text-align: inherit }

/* div.align-center * { */
/*   text-align: left } */

.align-top    {
  vertical-align: top }

.align-middle {
  vertical-align: middle }

.align-bottom {
  vertical-align: bottom }

ol.simple, ul.simple {
  margin-bottom: 1em }

ol.arabic {
  list-style: decimal }

ol.loweralpha {
  list-style: lower-alpha }

ol.upperalpha {
  list-style: upper-alpha }

ol.lowerroman {
  list-style: lower-roman }

ol.upperroman {
  list-style: upper-roman }

p.attribution {
  text-align: right ;
  margin-left: 50% }

p.caption {
  font-style: italic }

p.credits {
  font-style: italic ;
  font-size: smaller }

p.label {
  white-space: nowrap }

p.rubric {
  font-weight: bold ;
  font-size: larger ;
  color: maroon ;
  text-align: center }

p.sidebar-title {
  font-family: sans-serif ;
  font-weight: bold ;
  font-size: larger }

p.sidebar-subtitle {
  font-family: sans-serif ;
  font-weight: bold }

p.topic-title {
  font-weight: bold }

pre.address {
  margin-bottom: 0 ;
  margin-top: 0 ;
  font: inherit }

pre.literal-block, pre.doctest-block, pre.math, pre.code {
  margin-left: 2em ;
  margin-right: 2em }

pre.code .ln { color: gray; } /* line numbers */
pre.code, code { background-color: #eeeeee }
pre.code .comment, code .comment { color: #5C6576 }
pre.code .keyword, code .keyword { color: #3B0D06; font-weight: bold }
pre.code .literal.string, code .literal.string { color: #0C5404 }
pre.code .name.builtin, code .name.builtin { color: #352B84 }
pre.code .deleted, code .deleted { background-color: #DEB0A1}
pre.code .inserted, code .inserted { background-color: #A3D289}

span.classifier {
  font-family: sans-serif ;
  font-style: oblique }

span.classifier-delimiter {
  font-family: sans-serif ;
  font-weight: bold }

span.interpreted {
  font-family: sans-serif }

span.option {
  white-space: nowrap }

span.pre {
  white-space: pre }

span.problematic, pre.problematic {
  color: red }

span.section-subtitle {
  /* font-size relative to parent (h1..h6 element) */
  font-size: 80% }

table.citation {
  border-left: solid 1px gray;
  margin-left: 1px }

table.docinfo {
  margin: 2em 4em }

table.docutils {
  margin-top: 0.5em ;
  margin-bottom: 0.5em }

table.footnote {
  border-left: solid 1px black;
  margin-left: 1px }

table.docutils td, table.docutils th,
table.docinfo td, table.docinfo th {
  padding-left: 0.5em ;
  padding-right: 0.5em ;
  vertical-align: top }

table.docutils th.field-name, table.docinfo th.docinfo-name {
  font-weight: bold ;
  text-align: left ;
  white-space: nowrap ;
  padding-left: 0 }

/* "booktabs" style (no vertical lines) */
table.docutils.booktabs {
  border: 0px;
  border-top: 2px solid;
  border-bottom: 2px solid;
  border-collapse: collapse;
}
table.docutils.booktabs * {
  border: 0px;
}
table.docutils.booktabs th {
  border-bottom: thin solid;
  text-align: left;
}

h1 tt.docutils, h2 tt.docutils, h3 tt.docutils,
h4 tt.docutils, h5 tt.docutils, h6 tt.docutils {
  font-size: 100% }

ul.auto-toc {
  list-style-type: none }

</style>
</head>
<body>
<div class="document">


<a class="reference external image-reference" href="https://odoo-community.org/get-involved?utm_source=readme">
<img alt="Odoo Community Association" src="https://odoo-community.org/readme-banner-image" />
</a>
<div class="section" id="iot-base">
<h1>IoT Base</h1>
<!-- !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! This file is generated by oca-gen-addon-readme !!
!! changes will be overwritten.                   !!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! source digest: sha256:889ef99592819ed5b23b313ad174361e1a470b2db47d14f0908c41c7e61bf746
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! -->
<p><a class="reference external image-reference" href="https://odoo-community.org/page/development-status"><img alt="Beta" src="https://img.shields.io/badge/maturity-Beta-yellow.png" /></a> <a class="reference external image-reference" href="http://www.gnu.org/licenses/agpl-3.0-standalone.html"><img alt="License: AGPL-3" src="https://img.shields.io/badge/license-AGPL--3-blue.png" /></a> <a class="reference external image-reference" href="https://github.com/OCA/iot/tree/19.0/iot_oca"><img alt="OCA/iot" src="https://img.shields.io/badge/github-OCA%2Fiot-lightgray.png?logo=github" /></a> <a class="reference external image-reference" href="https://translation.odoo-community.org/projects/iot-19-0/iot-19-0-iot_oca"><img alt="Translate me on Weblate" src="https://img.shields.io/badge/weblate-Translate%20me-F47D42.png" /></a> <a class="reference external image-reference" href="https://runboat.odoo-community.org/builds?repo=OCA/iot&amp;target_branch=19.0"><img alt="Try me on Runboat" src="https://img.shields.io/badge/runboat-Try%20me-875A7B.png" /></a></p>
<p>This addon is a base module used for all iot modules.</p>
<p><strong>Table of contents</strong></p>
<div class="contents local topic" id="contents">
<ul class="simple">
<li><a class="reference internal" href="#bug-tracker" id="toc-entry-1">Bug Tracker</a></li>
<li><a class="reference internal" href="#credits" id="toc-entry-2">Credits</a><ul>
<li><a class="reference internal" href="#authors" id="toc-entry-3">Authors</a></li>
<li><a class="reference internal" href="#contributors" id="toc-entry-4">Contributors</a></li>
<li><a class="reference internal" href="#maintainers" id="toc-entry-5">Maintainers</a></li>
</ul>
</li>
</ul>
</div>
<div class="section" id="bug-tracker">
<h2><a class="toc-backref" href="#toc-entry-1">Bug Tracker</a></h2>
<p>Bugs are tracked on <a class="reference external" href="https://github.com/OCA/iot/issues">GitHub Issues</a>.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
<a class="reference external" href="https://github.com/OCA/iot/issues/new?body=module:%20iot_oca%0Aversion:%2019.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**">feedback</a>.</p>
<p>Do not contact contributors directly about support or help with technical issues.</p>
</div>
<div class="section" id="credits">
<h2><a class="toc-backref" href="#toc-entry-2">Credits</a></h2>
<div class="section" id="authors">
<h3><a class="toc-backref" href="#toc-entry-3">Authors</a></h3>
<ul class="simple">
<li>Creu Blanca</li>
</ul>
</div>
<div class="section" id="contributors">
<h3><a class="toc-backref" href="#toc-entry-4">Contributors</a></h3>
<ul class="simple">
<li>Enric Tobella &lt;<a class="reference external" href="mailto:etobella&#64;creublanca.es">etobella&#64;creublanca.es</a>&gt;</li>
<li>ViraWeb123 &lt;<a class="reference external" href="mailto:info&#64;viraweb123.ir">info&#64;viraweb123.ir</a>&gt;</li>
</ul>
</div>
<div class="section" id="maintainers">
<h3><a class="toc-backref" href="#toc-entry-5">Maintainers</a></h3>
<p>This module is maintained by the OCA.</p>
<a class="reference external image-reference" href="https://odoo-community.org">
<img alt="Odoo Community Association" src="https://odoo-community.org/logo.png" />
</a>
<p>OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.</p>
<p>This module is part of the <a class="reference external" href="https://github.com/OCA/iot/tree/19.0/iot_oca">OCA/iot</a> project on GitHub.</p>
<p>You are welcome to contribute. To learn how please visit <a class="reference external" href="https://odoo-community.org/page/Contribute">https://odoo-community.org/page/Contribute</a>.</p>
</div>
</div>
</div>
</div>
</body>
</html>

```

### File: `iot_oca/tests/__init__.py`
```python
from . import test_iot

```

### File: `iot_oca/tests/test_iot.py`
```python
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
        cls.device = cls.env["iot.device"].create(
            {"name": "Device", "communication_system_id": cls.system.id}
        )

    def test_action(self):
        self.assertEqual(self.device.action_count, 0)
        with mute_logger("odoo.addons.iot_oca.models.iot_communication_system_action"):
            self.device.with_context(
                iot_communication_system_action_id=self.action.id
            ).device_run_action()
        self.assertEqual(self.device.action_count, 1)
        self.assertEqual(self.device.action_ids.status, "failed")

    def test_correct_action(self):
        self.assertEqual(self.device.action_count, 0)
        with patch(
            "odoo.addons.iot_oca.models.iot_communication_system_action."
            "IoTSystemAction._run",
            return_value=("ok", ""),
        ):
            self.device.with_context(
                iot_communication_system_action_id=self.action.id
            ).device_run_action()
        self.assertEqual(self.device.action_count, 1)
        self.assertEqual(self.device.action_ids.status, "ok")

    def test_constrains(self):
        with self.assertRaises(ValidationError):
            self.device.with_context(
                iot_communication_system_action_id=self.action_2.id
            ).device_run_action()

    def test_rerun_failed_action(self):
        with mute_logger("odoo.addons.iot_oca.models.iot_communication_system_action"):
            self.device.with_context(
                iot_communication_system_action_id=self.action.id
            ).device_run_action()
        device_action = self.device.action_ids
        self.assertEqual(device_action.status, "failed")
        self.assertFalse(device_action.date_ok)
        with patch(
            "odoo.addons.iot_oca.models.iot_communication_system_action."
            "IoTSystemAction._run",
            return_value="done",
        ):
            device_action.run()
        self.assertEqual(device_action.status, "ok")
        self.assertEqual(device_action.result, "done")
        self.assertTrue(device_action.date_ok)

```

### File: `iot_oca/views/iot_device_group.xml`
```xml
<?xml version="1.0" encoding="utf-8" ?>
<!-- Copyright 2021 Creu Blanca
     License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). -->
<odoo>
    <record model="ir.ui.view" id="iot_device_group_form_view">
        <field name="name">iot.device.group.form (in iot_oca)</field>
        <field name="model">iot.device.group</field>
        <field name="arch" type="xml">
            <form>
                <header />
                <sheet>
                    <group>
                        <field name="name" />
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record model="ir.ui.view" id="iot_device_group_search_view">
        <field name="name">iot.device.group.search (in iot_oca)</field>
        <field name="model">iot.device.group</field>
        <field name="arch" type="xml">
            <search>
                <field name="name" />
            </search>
        </field>
    </record>
    <record model="ir.ui.view" id="iot_device_group_list_view">
        <field name="name">iot.device.group.list (in iot_oca)</field>
        <field name="model">iot.device.group</field>
        <field name="arch" type="xml">
            <list editable="bottom">
                <field name="name" />
            </list>
        </field>
    </record>
    <record model="ir.actions.act_window" id="iot_device_group_act_window">
        <field name="name">Device Group</field>
        <!-- TODO -->
        <field name="res_model">iot.device.group</field>
        <field name="view_mode">list,form</field>
        <field name="domain">[]</field>
        <field name="context">{}</field>
    </record>
    <record model="ir.ui.menu" id="iot_device_group_menu">
        <field name="name">Device Group</field>
        <field name="parent_id" ref="iot_configuration_menu" />
        <field name="action" ref="iot_device_group_act_window" />
        <field name="sequence" eval="10" />
    </record>
</odoo>

```

### File: `iot_oca/views/iot_device_tag.xml`
```xml
<?xml version="1.0" encoding="utf-8" ?>
<!-- Copyright 2021 Creu Blanca
     License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). -->
<odoo>
    <record model="ir.ui.view" id="iot_device_tag_form_view">
        <field name="name">iot.device.tag.form (in iot_oca)</field>
        <field name="model">iot.device.tag</field>
        <field name="arch" type="xml">
            <form>
                <header />
                <sheet>
                    <group>
                        <field name="name" />
                    </group>
                    <group name="main">
                        <field name="color" />
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record model="ir.ui.view" id="iot_device_tag_search_view">
        <field name="name">iot.device.tag.search (in iot_oca)</field>
        <field name="model">iot.device.tag</field>
        <field name="arch" type="xml">
            <search>
                <field name="name" />
            </search>
        </field>
    </record>
    <record model="ir.ui.view" id="iot_device_tag_list_view">
        <field name="name">iot.device.tag.list (in iot_oca)</field>
        <field name="model">iot.device.tag</field>
        <field name="arch" type="xml">
            <list editable="bottom">
                <field name="name" />
                <field name="color" />
            </list>
        </field>
    </record>
    <record model="ir.actions.act_window" id="iot_device_tag_act_window">
        <field name="name">Device Tag</field>
        <!-- TODO -->
        <field name="res_model">iot.device.tag</field>
        <field name="view_mode">list,form</field>
        <field name="domain">[]</field>
        <field name="context">{}</field>
    </record>
    <record model="ir.ui.menu" id="iot_device_tag_menu">
        <field name="name">Device Tag</field>
        <field name="parent_id" ref="iot_configuration_menu" />
        <field name="action" ref="iot_device_tag_act_window" />
        <field name="sequence" eval="20" />
    </record>
</odoo>

```

### File: `iot_oca/views/iot_device_views.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <record id="iot_device_list" model="ir.ui.view">
        <field name="name">iot.device.list</field>
        <field name="model">iot.device</field>
        <field name="arch" type="xml">
            <list delete="0">
                <field name="name" />
                <field name="communication_system_id" />
                <field name="model" />
                <field name="last_contact_date" />
                <field name="group_id" />
                <field name="ip" />
            </list>
        </field>
    </record>
    <record id="iot_device_form" model="ir.ui.view">
        <field name="name">iot.device.form</field>
        <field name="model">iot.device</field>
        <field name="arch" type="xml">
            <form>
                <header />
                <sheet>
                    <field name="active" invisible="1" />
                    <div class="oe_button_box" name="button_box" />
                    <widget
                        name="web_ribbon"
                        text="Archived"
                        bg_color="bg-danger"
                        invisible="active"
                    />
                    <field
                        name="image_1920"
                        widget='image'
                        class="oe_avatar"
                        options='{"preview_image": "image_128"}'
                    />
                    <div class="oe_title">
                        <h1>
                            <field name="name" />
                        </h1>
                    </div>
                    <group>
                        <group>
                            <field name="group_id" />
                            <field
                                name="tag_ids"
                                widget="many2many_tags"
                                options="{'color_field': 'color'}"
                            />
                            <field name="icon" />
                            <field
                                name="communication_system_id"
                                readonly="action_count"
                                widget="selection"
                            />
                            <field name="action_count" invisible="1" />
                        </group>
                        <group>
                            <field name="model" />
                            <field name="ip" />
                            <field name="state" />
                            <field name="last_contact_date" />
                        </group>
                    </group>
                    <notebook>
                        <page string="Actions" id="actions">
                            <field name="action_ids" readonly="True" />
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>
    <record id="iot_device_action_list" model="ir.ui.view">
        <field name="name">iot.device.action.list</field>
        <field name="model">iot.device.action</field>
        <field name="arch" type="xml">
            <list>
                <field name="status" />
                <field name="result" />
                <field name="date_ok" />
                <button
                    name="run"
                    type="object"
                    string="Run"
                    invisible="status == 'ok'"
                />
            </list>
        </field>
    </record>
    <record id="iot_device_kanban" model="ir.ui.view">
        <field name="name">iot.device.kanban</field>
        <field name="model">iot.device</field>
        <field name="arch" type="xml">
            <kanban highlight_color="color">
                <field name="id" />
                <field name="image_128" />
                <field name="icon" />
                <templates>
                    <t t-name="menu">
                        <a
                            t-if="widget.editable"
                            role="menuitem"
                            type="open"
                            class="dropdown-item"
                        >Edit</a>
                        <a
                            t-if="widget.deletable"
                            role="menuitem"
                            type="delete"
                            class="dropdown-item"
                        >Delete</a>
                        <field name="color" widget="kanban_color_picker" />
                    </t>
                    <t t-name="card" class="flex-row">
                        <aside class="o_kanban_aside_full me-2">
                            <field
                                t-if="record.image_128.raw_value"
                                name="image_128"
                                widget="image"
                                alt="Device image"
                            />
                            <i
                                t-elif="record.icon.raw_value"
                                t-attf-class="{{record.icon.raw_value}}"
                                title="Device icon"
                            />
                            <i
                                t-else=""
                                class="fa fa-question fa-6x"
                                title="Unknown device"
                            />
                        </aside>
                        <main>
                            <field name="name" class="fw-bold fs-5" />
                            <field t-if="record.group_id.raw_value" name="group_id" />
                            <div t-if="record.ip.raw_value">IP: <field
                                name="ip"
                            /></div>
                            <div t-if="record.last_contact_date.raw_value">
                                Last contact: <field name="last_contact_date" />
                            </div>
                            <field
                                name="tag_ids"
                                widget="many2many_tags"
                                options="{'color_field': 'color'}"
                            />
                            <div id="actions" />
                        </main>
                    </t>
                </templates>
            </kanban>
        </field>
    </record>
    <record id="iot_device_search" model="ir.ui.view">
        <field name="name">iot.device.search</field>
        <field name="model">iot.device</field>
        <field name="arch" type="xml">
            <search string="IoT Device Search">
                <field name="name" />
                <field name="group_id" />
                <field name="model" />
                <field name="ip" />
                <separator />
                <filter
                    name="active"
                    string="Active"
                    domain="[('active','=',True)]"
                    help="Active"
                />
                <filter
                    name="inactive"
                    string="Inactive"
                    domain="[('active','=',False)]"
                    help="Inactive"
                />
                <separator />
                <group>
                    <filter
                        name="group_group"
                        string="Group"
                        domain="[]"
                        context="{'group_by':'group_id'}"
                    />
                </group>
            </search>
        </field>
    </record>
    <record model="ir.actions.act_window" id="iot_device_action">
        <field name="name">IoT Devices</field>
        <field name="type">ir.actions.act_window</field>
        <field name="res_model">iot.device</field>
        <field name="view_mode">kanban,list,form</field>
    </record>
    <menuitem
        name="Devices"
        sequence="10"
        id="iot_device_menu"
        action="iot_device_action"
        parent="iot_root_menu"
    />
</odoo>

```

### File: `iot_oca/views/iot_menu.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <menuitem
        name="IoT"
        id="iot_root_menu"
        groups="group_iot_user"
        web_icon="iot_oca,static/description/icon.png"
    />
    <record model="ir.ui.menu" id="iot_configuration_menu">
        <field name="name">Configuration</field>
        <field name="parent_id" ref="iot_root_menu" />
        <field name="sequence" eval="20" />
        <field name="group_ids" eval="[(4, ref('group_iot_manager'))]" />
    </record>
</odoo>

```

### File: `iot_oca/views/iot_system_views.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <record id="iot_system_list" model="ir.ui.view">
        <field name="name">iot.communication.system.list</field>
        <field name="model">iot.communication.system</field>
        <field name="arch" type="xml">
            <list create="0" delete="0">
                <field name="name" />
            </list>
        </field>
    </record>
    <record id="iot_system_form" model="ir.ui.view">
        <field name="name">iot.communication.system.form</field>
        <field name="model">iot.communication.system</field>
        <field name="arch" type="xml">
            <form create="0" delete="0" edit="0">
                <header />
                <sheet>
                    <div class="oe_title">
                        <h1>
                            <field name="name" />
                        </h1>
                    </div>
                    <notebook>
                        <page string="Devices" id="devices">
                            <field name="device_ids" readonly="True" />
                        </page>
                        <page string="Actions" id="actions">
                            <field
                                name="communication_system_action_ids"
                                readonly="True"
                            />
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>
    <record id="iot_system_action_list" model="ir.ui.view">
        <field name="name">iot.communication.system.action.list</field>
        <field name="model">iot.communication.system.action</field>
        <field name="arch" type="xml">
            <list create="0" delete="0">
                <field name="name" />
            </list>
        </field>
    </record>
    <record model="ir.actions.act_window" id="iot_system_action">
        <field name="name">IoT System</field>
        <field name="type">ir.actions.act_window</field>
        <field name="res_model">iot.communication.system</field>
        <field name="view_mode">list,form</field>
    </record>
    <menuitem
        name="Systems"
        sequence="90"
        id="iot_system_menu"
        action="iot_system_action"
        parent="iot_configuration_menu"
        groups="group_iot_manager"
    />
</odoo>

```

### File: `iot_output_oca/__init__.py`
```python
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from . import models

```

### File: `iot_output_oca/__manifest__.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "IoT Output",
    "version": "19.0.1.0.0",
    "category": "IoT",
    "author": "Creu Blanca, " "Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "installable": True,
    "application": True,
    "summary": "IoT allow multiple outputs",
    "website": "https://github.com/OCA/iot",
    "depends": ["iot_oca"],
    "data": [
        "security/ir.model.access.csv",
        "views/iot_device_output_views.xml",
        "views/iot_device_views.xml",
    ],
}

```

### File: `iot_output_oca/models/__init__.py`
```python
from . import iot_device
from . import iot_device_output_action
from . import iot_device_output
from . import iot_communication_system

```

### File: `iot_output_oca/models/iot_communication_system.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class IoTCommunicationSystem(models.Model):
    _inherit = "iot.communication.system"

    output_ids = fields.One2many(
        "iot.device.output", inverse_name="communication_system_id"
    )
    applies_to = fields.Selection(
        [("device", "Device"), ("output", "Output")], default="device", required=True
    )

```

### File: `iot_output_oca/models/iot_device_output_action.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IoTDeviceOutputAction(models.Model):
    _name = "iot.device.output.action"
    _description = "IoT Action"
    _order = "date_ok desc"

    output_id = fields.Many2one("iot.device.output", required=True, readonly=True)
    communication_system_action_id = fields.Many2one(
        "iot.communication.system.action", required=True
    )
    status = fields.Selection(
        [("ok", "Ok"), ("pending", "Pending"), ("failed", "Failed")],
        required=True,
        default="pending",
    )
    result = fields.Text()
    date_ok = fields.Datetime(readonly=True, string="Ok date")

    @api.constrains("output_id", "communication_system_action_id")
    def _check_system(self):
        if self.filtered(
            lambda r: r.output_id.communication_system_id
            != r.communication_system_action_id.communication_system_id
        ):
            raise ValidationError(_("Device and action must be of the same system"))

    def run_extra_actions(self, status, result):
        return

    def run(self):
        self.ensure_one()
        if self.status != "ok":
            status, result = self.communication_system_action_id.run(self)
            self.write(
                {
                    "status": status,
                    "result": result,
                    "date_ok": fields.Datetime.now() if status == "ok" else False,
                }
            )
            self.run_extra_actions(status, result)

```

### File: `iot_output_oca/models/iot_device_output.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class IoTDevice(models.Model):
    _name = "iot.device.output"
    _description = "IoT Device"

    name = fields.Char(required=True)
    device_id = fields.Many2one(
        "iot.device", required=True, readonly=True, bypass_search_access=True
    )
    communication_system_id = fields.Many2one("iot.communication.system", required=True)
    action_ids = fields.One2many("iot.device.output.action", inverse_name="output_id")
    state = fields.Selection([], readonly=True)
    model = fields.Char()
    ip = fields.Char()
    action_count = fields.Integer(compute="_compute_action_count")

    @api.depends("action_ids")
    def _compute_action_count(self):
        for record in self:
            record.action_count = len(record.action_ids)

    def _system_action_vals(self, system_action):
        return {
            "output_id": self.id,
            "communication_system_action_id": system_action.id,
        }

    def device_run_action(self):
        system_action = self.env["iot.communication.system.action"].browse(
            self.env.context.get("iot_communication_system_action_id")
        )
        for rec in self:
            if not self.device_id.active:
                continue
            action = self.env["iot.device.output.action"].create(
                rec._system_action_vals(system_action)
            )
            action.run()
            self.device_id.last_contact_date = fields.Datetime.now()

```

### File: `iot_output_oca/models/iot_device.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class IoTDevice(models.Model):
    _inherit = "iot.device"

    output_ids = fields.One2many("iot.device.output", inverse_name="device_id")
    output_count = fields.Integer(compute="_compute_output_count")
    communication_system_id = fields.Many2one(required=False)

    @api.depends("output_ids")
    def _compute_output_count(self):
        for record in self:
            record.output_count = len(record.output_ids)

    def action_show_output(self):
        self.ensure_one()
        action = self.env.ref("iot_output_oca.iot_device_output_action")
        result = action.read()[0]

        result["context"] = {
            "default_device_id": self.id,
        }
        result["domain"] = "[('device_id', '=', " + str(self.id) + ")]"
        if len(self.output_ids) == 1:
            result["views"] = [(False, "form")]
            result["res_id"] = self.output_ids.id
        return result

```

### File: `iot_output_oca/pyproject.toml`
```toml
[build-system]
requires = ["whool"]
build-backend = "whool.buildapi"

```

### File: `iot_output_oca/security/ir.model.access.csv`
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_iot_device_output_action,access_iot_device_output_action,model_iot_device_output_action,iot_oca.group_iot_user,1,1,1,0
access_iot_device_output,access_iot_device_output,model_iot_device_output,iot_oca.group_iot_user,1,0,0,0
manage_iot_device_output,access_iot_device_output,model_iot_device_output,iot_oca.group_iot_manager,1,1,1,0

```

### File: `iot_output_oca/static/description/index.html`
```text
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<meta name="generator" content="Docutils: https://docutils.sourceforge.io/" />
<title>IoT Output</title>
<style type="text/css">

/*
:Author: David Goodger (goodger@python.org)
:Id: $Id: html4css1.css 9511 2024-01-13 09:50:07Z milde $
:Copyright: This stylesheet has been placed in the public domain.

Default cascading style sheet for the HTML output of Docutils.
Despite the name, some widely supported CSS2 features are used.

See https://docutils.sourceforge.io/docs/howto/html-stylesheets.html for how to
customize this style sheet.
*/

/* used to remove borders from tables and images */
.borderless, table.borderless td, table.borderless th {
  border: 0 }

table.borderless td, table.borderless th {
  /* Override padding for "table.docutils td" with "! important".
     The right padding separates the table cells. */
  padding: 0 0.5em 0 0 ! important }

.first {
  /* Override more specific margin styles with "! important". */
  margin-top: 0 ! important }

.last, .with-subtitle {
  margin-bottom: 0 ! important }

.hidden {
  display: none }

.subscript {
  vertical-align: sub;
  font-size: smaller }

.superscript {
  vertical-align: super;
  font-size: smaller }

a.toc-backref {
  text-decoration: none ;
  color: black }

blockquote.epigraph {
  margin: 2em 5em ; }

dl.docutils dd {
  margin-bottom: 0.5em }

object[type="image/svg+xml"], object[type="application/x-shockwave-flash"] {
  overflow: hidden;
}

/* Uncomment (and remove this text!) to get bold-faced definition list terms
dl.docutils dt {
  font-weight: bold }
*/

div.abstract {
  margin: 2em 5em }

div.abstract p.topic-title {
  font-weight: bold ;
  text-align: center }

div.admonition, div.attention, div.caution, div.danger, div.error,
div.hint, div.important, div.note, div.tip, div.warning {
  margin: 2em ;
  border: medium outset ;
  padding: 1em }

div.admonition p.admonition-title, div.hint p.admonition-title,
div.important p.admonition-title, div.note p.admonition-title,
div.tip p.admonition-title {
  font-weight: bold ;
  font-family: sans-serif }

div.attention p.admonition-title, div.caution p.admonition-title,
div.danger p.admonition-title, div.error p.admonition-title,
div.warning p.admonition-title, .code .error {
  color: red ;
  font-weight: bold ;
  font-family: sans-serif }

/* Uncomment (and remove this text!) to get reduced vertical space in
   compound paragraphs.
div.compound .compound-first, div.compound .compound-middle {
  margin-bottom: 0.5em }

div.compound .compound-last, div.compound .compound-middle {
  margin-top: 0.5em }
*/

div.dedication {
  margin: 2em 5em ;
  text-align: center ;
  font-style: italic }

div.dedication p.topic-title {
  font-weight: bold ;
  font-style: normal }

div.figure {
  margin-left: 2em ;
  margin-right: 2em }

div.footer, div.header {
  clear: both;
  font-size: smaller }

div.line-block {
  display: block ;
  margin-top: 1em ;
  margin-bottom: 1em }

div.line-block div.line-block {
  margin-top: 0 ;
  margin-bottom: 0 ;
  margin-left: 1.5em }

div.sidebar {
  margin: 0 0 0.5em 1em ;
  border: medium outset ;
  padding: 1em ;
  background-color: #ffffee ;
  width: 40% ;
  float: right ;
  clear: right }

div.sidebar p.rubric {
  font-family: sans-serif ;
  font-size: medium }

div.system-messages {
  margin: 5em }

div.system-messages h1 {
  color: red }

div.system-message {
  border: medium outset ;
  padding: 1em }

div.system-message p.system-message-title {
  color: red ;
  font-weight: bold }

div.topic {
  margin: 2em }

h1.section-subtitle, h2.section-subtitle, h3.section-subtitle,
h4.section-subtitle, h5.section-subtitle, h6.section-subtitle {
  margin-top: 0.4em }

h1.title {
  text-align: center }

h2.subtitle {
  text-align: center }

hr.docutils {
  width: 75% }

img.align-left, .figure.align-left, object.align-left, table.align-left {
  clear: left ;
  float: left ;
  margin-right: 1em }

img.align-right, .figure.align-right, object.align-right, table.align-right {
  clear: right ;
  float: right ;
  margin-left: 1em }

img.align-center, .figure.align-center, object.align-center {
  display: block;
  margin-left: auto;
  margin-right: auto;
}

table.align-center {
  margin-left: auto;
  margin-right: auto;
}

.align-left {
  text-align: left }

.align-center {
  clear: both ;
  text-align: center }

.align-right {
  text-align: right }

/* reset inner alignment in figures */
div.align-right {
  text-align: inherit }

/* div.align-center * { */
/*   text-align: left } */

.align-top    {
  vertical-align: top }

.align-middle {
  vertical-align: middle }

.align-bottom {
  vertical-align: bottom }

ol.simple, ul.simple {
  margin-bottom: 1em }

ol.arabic {
  list-style: decimal }

ol.loweralpha {
  list-style: lower-alpha }

ol.upperalpha {
  list-style: upper-alpha }

ol.lowerroman {
  list-style: lower-roman }

ol.upperroman {
  list-style: upper-roman }

p.attribution {
  text-align: right ;
  margin-left: 50% }

p.caption {
  font-style: italic }

p.credits {
  font-style: italic ;
  font-size: smaller }

p.label {
  white-space: nowrap }

p.rubric {
  font-weight: bold ;
  font-size: larger ;
  color: maroon ;
  text-align: center }

p.sidebar-title {
  font-family: sans-serif ;
  font-weight: bold ;
  font-size: larger }

p.sidebar-subtitle {
  font-family: sans-serif ;
  font-weight: bold }

p.topic-title {
  font-weight: bold }

pre.address {
  margin-bottom: 0 ;
  margin-top: 0 ;
  font: inherit }

pre.literal-block, pre.doctest-block, pre.math, pre.code {
  margin-left: 2em ;
  margin-right: 2em }

pre.code .ln { color: gray; } /* line numbers */
pre.code, code { background-color: #eeeeee }
pre.code .comment, code .comment { color: #5C6576 }
pre.code .keyword, code .keyword { color: #3B0D06; font-weight: bold }
pre.code .literal.string, code .literal.string { color: #0C5404 }
pre.code .name.builtin, code .name.builtin { color: #352B84 }
pre.code .deleted, code .deleted { background-color: #DEB0A1}
pre.code .inserted, code .inserted { background-color: #A3D289}

span.classifier {
  font-family: sans-serif ;
  font-style: oblique }

span.classifier-delimiter {
  font-family: sans-serif ;
  font-weight: bold }

span.interpreted {
  font-family: sans-serif }

span.option {
  white-space: nowrap }

span.pre {
  white-space: pre }

span.problematic, pre.problematic {
  color: red }

span.section-subtitle {
  /* font-size relative to parent (h1..h6 element) */
  font-size: 80% }

table.citation {
  border-left: solid 1px gray;
  margin-left: 1px }

table.docinfo {
  margin: 2em 4em }

table.docutils {
  margin-top: 0.5em ;
  margin-bottom: 0.5em }

table.footnote {
  border-left: solid 1px black;
  margin-left: 1px }

table.docutils td, table.docutils th,
table.docinfo td, table.docinfo th {
  padding-left: 0.5em ;
  padding-right: 0.5em ;
  vertical-align: top }

table.docutils th.field-name, table.docinfo th.docinfo-name {
  font-weight: bold ;
  text-align: left ;
  white-space: nowrap ;
  padding-left: 0 }

/* "booktabs" style (no vertical lines) */
table.docutils.booktabs {
  border: 0px;
  border-top: 2px solid;
  border-bottom: 2px solid;
  border-collapse: collapse;
}
table.docutils.booktabs * {
  border: 0px;
}
table.docutils.booktabs th {
  border-bottom: thin solid;
  text-align: left;
}

h1 tt.docutils, h2 tt.docutils, h3 tt.docutils,
h4 tt.docutils, h5 tt.docutils, h6 tt.docutils {
  font-size: 100% }

ul.auto-toc {
  list-style-type: none }

</style>
</head>
<body>
<div class="document">


<a class="reference external image-reference" href="https://odoo-community.org/get-involved?utm_source=readme">
<img alt="Odoo Community Association" src="https://odoo-community.org/readme-banner-image" />
</a>
<div class="section" id="iot-output">
<h1>IoT Output</h1>
<!-- !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! This file is generated by oca-gen-addon-readme !!
!! changes will be overwritten.                   !!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! source digest: sha256:afc577c766111171c8fb2ad306f2f90a23dc39b72915a33e9f231c4784c92dff
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! -->
<p><a class="reference external image-reference" href="https://odoo-community.org/page/development-status"><img alt="Beta" src="https://img.shields.io/badge/maturity-Beta-yellow.png" /></a> <a class="reference external image-reference" href="http://www.gnu.org/licenses/agpl-3.0-standalone.html"><img alt="License: AGPL-3" src="https://img.shields.io/badge/license-AGPL--3-blue.png" /></a> <a class="reference external image-reference" href="https://github.com/OCA/iot/tree/18.0/iot_output_oca"><img alt="OCA/iot" src="https://img.shields.io/badge/github-OCA%2Fiot-lightgray.png?logo=github" /></a> <a class="reference external image-reference" href="https://translation.odoo-community.org/projects/iot-18-0/iot-18-0-iot_output_oca"><img alt="Translate me on Weblate" src="https://img.shields.io/badge/weblate-Translate%20me-F47D42.png" /></a> <a class="reference external image-reference" href="https://runboat.odoo-community.org/builds?repo=OCA/iot&amp;target_branch=18.0"><img alt="Try me on Runboat" src="https://img.shields.io/badge/runboat-Try%20me-875A7B.png" /></a></p>
<p>This addon is a base module used to allow different outputs from the
same device</p>
<p><strong>Table of contents</strong></p>
<div class="contents local topic" id="contents">
<ul class="simple">
<li><a class="reference internal" href="#bug-tracker" id="toc-entry-1">Bug Tracker</a></li>
<li><a class="reference internal" href="#credits" id="toc-entry-2">Credits</a><ul>
<li><a class="reference internal" href="#authors" id="toc-entry-3">Authors</a></li>
<li><a class="reference internal" href="#contributors" id="toc-entry-4">Contributors</a></li>
<li><a class="reference internal" href="#maintainers" id="toc-entry-5">Maintainers</a></li>
</ul>
</li>
</ul>
</div>
<div class="section" id="bug-tracker">
<h2><a class="toc-backref" href="#toc-entry-1">Bug Tracker</a></h2>
<p>Bugs are tracked on <a class="reference external" href="https://github.com/OCA/iot/issues">GitHub Issues</a>.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
<a class="reference external" href="https://github.com/OCA/iot/issues/new?body=module:%20iot_output_oca%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**">feedback</a>.</p>
<p>Do not contact contributors directly about support or help with technical issues.</p>
</div>
<div class="section" id="credits">
<h2><a class="toc-backref" href="#toc-entry-2">Credits</a></h2>
<div class="section" id="authors">
<h3><a class="toc-backref" href="#toc-entry-3">Authors</a></h3>
<ul class="simple">
<li>Creu Blanca</li>
</ul>
</div>
<div class="section" id="contributors">
<h3><a class="toc-backref" href="#toc-entry-4">Contributors</a></h3>
<ul class="simple">
<li>Enric Tobella &lt;<a class="reference external" href="mailto:etobella&#64;creublanca.es">etobella&#64;creublanca.es</a>&gt;</li>
</ul>
</div>
<div class="section" id="maintainers">
<h3><a class="toc-backref" href="#toc-entry-5">Maintainers</a></h3>
<p>This module is maintained by the OCA.</p>
<a class="reference external image-reference" href="https://odoo-community.org">
<img alt="Odoo Community Association" src="https://odoo-community.org/logo.png" />
</a>
<p>OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.</p>
<p>This module is part of the <a class="reference external" href="https://github.com/OCA/iot/tree/18.0/iot_output_oca">OCA/iot</a> project on GitHub.</p>
<p>You are welcome to contribute. To learn how please visit <a class="reference external" href="https://odoo-community.org/page/Contribute">https://odoo-community.org/page/Contribute</a>.</p>
</div>
</div>
</div>
</div>
</body>
</html>

```

### File: `iot_output_oca/tests/__init__.py`
```python
from . import test_iot

```

### File: `iot_output_oca/tests/test_iot.py`
```python
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

```

### File: `iot_output_oca/views/iot_device_output_views.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <record id="iot_device_output_list" model="ir.ui.view">
        <field name="name">iot.device.output.list</field>
        <field name="model">iot.device.output</field>
        <field name="arch" type="xml">
            <list delete="0">
                <field name="name" />
                <field name="communication_system_id" />
            </list>
        </field>
    </record>
    <record id="iot_device_output_form" model="ir.ui.view">
        <field name="name">iot.device.output.form</field>
        <field name="model">iot.device.output</field>
        <field name="arch" type="xml">
            <form>
                <header />
                <sheet>
                    <div class="oe_button_box" name="button_box" />
                    <div class="oe_title">
                        <h1>
                            <field name="name" />
                        </h1>
                    </div>
                    <group>
                        <group>
                            <field
                                name="communication_system_id"
                                domain="[('applies_to', '=', 'output')]"
                            />
                        </group>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record model="ir.actions.act_window" id="iot_device_output_action">
        <field name="name">IoT Outputs</field>
        <field name="type">ir.actions.act_window</field>
        <field name="res_model">iot.device.output</field>
        <field name="view_mode">list,form</field>
    </record>
    <record id="iot_device_output_action_list" model="ir.ui.view">
        <field name="name">iot.device.output.action.list</field>
        <field name="model">iot.device.output.action</field>
        <field name="arch" type="xml">
            <list create="0" delete="0">
                <field name="status" />
                <field name="result" />
                <field name="date_ok" />
                <button
                    name="run"
                    type="object"
                    string="Run"
                    invisible="status == 'ok'"
                />
            </list>
        </field>
    </record>
</odoo>

```

### File: `iot_output_oca/views/iot_device_views.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <record id="iot_device_form" model="ir.ui.view">
        <field name="name">iot.device.form</field>
        <field name="model">iot.device</field>
        <field name="inherit_id" ref="iot_oca.iot_device_form" />
        <field name="arch" type="xml">
            <xpath expr="//div[@name='button_box']" position="inside">
                <button
                    name="action_show_output"
                    type="object"
                    class="oe_stat_button"
                    icon="fa-terminal"
                >
                    <field string="Outputs" name="output_count" widget="statinfo" />
                </button>
            </xpath>
            <field name="communication_system_id" position="attributes">
                <attribute name="domain">[('applies_to', '=', 'device')]</attribute>
            </field>
            <page id="actions" position="attributes">
                <attribute name="invisible">not communication_system_id</attribute>
            </page>
        </field>
    </record>

    <record id="iot_device_kanban" model="ir.ui.view">
        <field name="name">iot.device.kanban</field>
        <field name="model">iot.device</field>
        <field name="inherit_id" ref="iot_oca.iot_device_kanban" />
        <field name="arch" type="xml">
            <xpath expr="//div[@role='menu']/*[1]" position="before">
                <a
                    type="object"
                    name="action_show_output"
                    role="menuitem"
                    class="dropdown-item"
                >
                    <i class="fa fa-terminal" />
                    Outputs
                </a>
            </xpath>
        </field>
    </record>
</odoo>

```

### File: `iot_template_oca/controller/__init__.py`
```python
from . import iot_controller

```

### File: `iot_template_oca/controller/iot_controller.py`
```python
# Copyright 2020 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from odoo import http


class CallIot(http.Controller):
    @http.route(
        ["/iot/<serial>/configure"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def configure_iot(self, serial, template, **kwargs):
        request = http.request
        if not request.env:
            return json.dumps(False)
        return json.dumps(
            request.env["iot.device.configure"]
            .sudo()
            .configure(serial, template, **kwargs)
        )

```

### File: `iot_template_oca/demo/iot_template.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <record id="demo_template" model="iot.template">
        <field name="name">demo_template</field>
    </record>
    <record id="demo_template_serial" model="iot.template.key">
        <field name="template_id" ref="demo_template" />
        <field name="key">serial</field>
    </record>
    <record id="demo_template_input" model="iot.template.input">
        <field name="template_id" ref="demo_template" />
        <field name="name">demo_input</field>
        <field name="call_model_id" eval="False" />
        <field name="call_function">test_input_device</field>
        <field name="params">{}</field>
    </record>
</odoo>

```

### File: `iot_template_oca/__init__.py`
```python
from . import controller
from . import models
from . import wizards

```

### File: `iot_template_oca/__manifest__.py`
```python
# Copyright (C) 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "IoT Templates",
    "version": "19.0.1.0.0",
    "category": "IoT",
    "author": "Creu Blanca, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "installable": True,
    "summary": "IoT module for managing templates",
    "depends": ["iot_input_oca", "iot_output_oca"],
    "website": "https://github.com/OCA/iot",
    "data": [
        "security/ir.model.access.csv",
        "wizards/iot_device_configure.xml",
        "views/iot_template_views.xml",
    ],
    "demo": ["demo/iot_template.xml"],
}

```

### File: `iot_template_oca/models/__init__.py`
```python
from . import iot_device
from . import iot_device_input
from . import iot_device_output
from . import iot_template

```

### File: `iot_template_oca/models/iot_device_input.py`
```python
# Copyright 2020 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class IotDeviceInput(models.Model):
    _inherit = "iot.device.input"

    template_input_id = fields.Many2one(
        "iot.template.input",
        readonly=True,
    )

    def get_configuration(self):
        return {
            "serial": self.serial,
            "passphrase": self.passphrase,
        }

```

### File: `iot_template_oca/models/iot_device_output.py`
```python
# Copyright 2020 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class IotDeviceOutput(models.Model):
    _inherit = "iot.device.output"

    template_output_id = fields.Many2one(
        "iot.template.output",
        readonly=True,
    )

    def get_configuration(self):
        return {}

```

### File: `iot_template_oca/models/iot_device.py`
```python
# Copyright 2020 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class IotDevice(models.Model):
    _inherit = "iot.device"

    def get_iot_configuration(self):
        self.ensure_one()
        return {
            "host": self.env["ir.config_parameter"].sudo().get_param("web.base.url"),
            "name": self.name,
            "outputs": {
                output.name: output.get_configuration() for output in self.output_ids
            },
            "inputs": {
                iot_input.name: iot_input.get_configuration()
                for iot_input in self.input_ids
            },
        }

```

### File: `iot_template_oca/models/iot_template.py`
```python
# Copyright 2020 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from uuid import uuid4

from jinja2.sandbox import SandboxedEnvironment

from odoo import fields, models
from odoo.tools.safe_eval import safe_eval

mako_template_env = SandboxedEnvironment(
    block_start_string="<%",
    block_end_string="%>",
    variable_start_string="${",
    variable_end_string="}",
    comment_start_string="<%doc>",
    comment_end_string="</%doc>",
    line_statement_prefix="%",
    line_comment_prefix="##",
    trim_blocks=True,  # do not output newline after blocks
    autoescape=True,  # XML/HTML automatic escaping
)


class IotTemplate(models.Model):
    _name = "iot.template"
    _inherit = "image.mixin"
    _description = "IoT Template for Device"
    _parent_name = "parent_id"
    _parent_store = True
    _parent_order = "name"

    parent_path = fields.Char(index=True)
    name = fields.Char(required=True)
    input_ids = fields.One2many(
        "iot.template.input",
        inverse_name="template_id",
    )
    output_ids = fields.One2many(
        "iot.template.output",
        inverse_name="template_id",
    )
    key_ids = fields.One2many("iot.template.key", inverse_name="template_id")
    parent_id = fields.Many2one("iot.template", ondelete="restrict")
    tag_ids = fields.Many2many("iot.device.tag")
    group_id = fields.Many2one("iot.device.group")
    icon = fields.Selection(
        selection=lambda r: r.env["iot.device"]._fields["icon"].selection
    )

    def _get_keys(self, serial):
        if self.parent_id:
            keys = self.parent_id._get_keys(serial)
        else:
            keys = {"serial": serial}
        keys.update({key.key: key._generate_value() for key in self.key_ids})
        return keys

    def apply_template(self, device, keys):
        self.ensure_one()
        new_vals = {}
        if self.group_id and not device.group_id:
            new_vals["group_id"] = self.group_id.id
        if self.tag_ids:
            new_vals["tag_ids"] = [(4, tag_id) for tag_id in self.tag_ids.ids]
        if self.image_1920 and not device.image_1920:
            new_vals["image_1920"] = self.image_1920
        if self.icon and not device.icon:
            new_vals["icon"] = self.icon
        if new_vals:
            device.write(new_vals)
        for element in self.input_ids:
            element._apply_template(device, keys)
        for element in self.output_ids:
            element._apply_template(device, keys)
        if self.parent_id:
            self.parent_id.apply_template(device, keys)


class IotTemplateInput(models.Model):
    _name = "iot.template.input"
    _description = "IoT Input for Template"

    template_id = fields.Many2one("iot.template", required=True)
    name = fields.Char(required=True)
    params = fields.Text()
    call_model_id = fields.Many2one("ir.model")
    call_function = fields.Char(required=True)

    def _apply_template(self, device, keys):
        real_vals = {
            "device_id": device.id,
            "name": self.name,
            "call_function": self.call_function,
            "call_model_id": self.call_model_id.id,
            "template_input_id": self.id,
            "serial": uuid4(),
            "passphrase": uuid4(),
        }
        vals = safe_eval(self.params)
        for key in vals:
            vals[key] = mako_template_env.from_string(vals[key]).render(keys)
        real_vals.update(vals)
        return self.env["iot.device.input"].create(real_vals)


class IotTemplateOutput(models.Model):
    _name = "iot.template.output"
    _description = "Output templates for IoT"

    template_id = fields.Many2one("iot.template", required=True)
    name = fields.Char(required=True)
    communication_system_id = fields.Many2one("iot.communication.system", required=True)
    params = fields.Text()

    def _apply_template(self, device, keys):
        real_vals = {
            "device_id": device.id,
            "name": self.name,
            "communication_system_id": self.communication_system_id.id,
            "template_output_id": self.id,
        }
        vals = safe_eval(self.params or "{}")
        for key in vals:
            vals[key] = mako_template_env.from_string(vals[key]).render(keys)
        real_vals.update(vals)
        return self.env["iot.device.output"].create(real_vals)


class IotTemplateKey(models.Model):
    _name = "iot.template.key"
    _description = "IoT Keys for configuration"

    template_id = fields.Many2one("iot.template", required=True)
    key = fields.Char(required=True)

    def _generate_value(self):
        return uuid4()

```

### File: `iot_template_oca/pyproject.toml`
```toml
[build-system]
requires = ["whool"]
build-backend = "whool.buildapi"

```

### File: `iot_template_oca/security/ir.model.access.csv`
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_iot_template,access_iot_template,model_iot_template,iot_oca.group_iot_user,1,0,0,0
manage_iot_template,access_iot_template,model_iot_template,iot_oca.group_iot_manager,1,1,1,1
access_iot_template_input,access_iot_template_input,model_iot_template_input,iot_oca.group_iot_user,1,0,0,0
manage_iot_template_input,access_iot_template_input,model_iot_template_input,iot_oca.group_iot_manager,1,1,1,1
access_iot_template_output,access_iot_template_output,model_iot_template_output,iot_oca.group_iot_user,1,0,0,0
manage_iot_template_output,access_iot_template_output,model_iot_template_output,iot_oca.group_iot_manager,1,1,1,1
access_iot_template_key,access_iot_template_key,model_iot_template_key,iot_oca.group_iot_user,1,0,0,0
manage_iot_template_key,access_iot_template_key,model_iot_template_key,iot_oca.group_iot_manager,1,1,1,1
access_iot_device_configure,access_iot_device_configure,model_iot_device_configure,iot_oca.group_iot_manager,1,1,1,1

```

### File: `iot_template_oca/static/description/index.html`
```text
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<meta name="generator" content="Docutils: https://docutils.sourceforge.io/" />
<title>IoT Templates</title>
<style type="text/css">

/*
:Author: David Goodger (goodger@python.org)
:Id: $Id: html4css1.css 9511 2024-01-13 09:50:07Z milde $
:Copyright: This stylesheet has been placed in the public domain.

Default cascading style sheet for the HTML output of Docutils.
Despite the name, some widely supported CSS2 features are used.

See https://docutils.sourceforge.io/docs/howto/html-stylesheets.html for how to
customize this style sheet.
*/

/* used to remove borders from tables and images */
.borderless, table.borderless td, table.borderless th {
  border: 0 }

table.borderless td, table.borderless th {
  /* Override padding for "table.docutils td" with "! important".
     The right padding separates the table cells. */
  padding: 0 0.5em 0 0 ! important }

.first {
  /* Override more specific margin styles with "! important". */
  margin-top: 0 ! important }

.last, .with-subtitle {
  margin-bottom: 0 ! important }

.hidden {
  display: none }

.subscript {
  vertical-align: sub;
  font-size: smaller }

.superscript {
  vertical-align: super;
  font-size: smaller }

a.toc-backref {
  text-decoration: none ;
  color: black }

blockquote.epigraph {
  margin: 2em 5em ; }

dl.docutils dd {
  margin-bottom: 0.5em }

object[type="image/svg+xml"], object[type="application/x-shockwave-flash"] {
  overflow: hidden;
}

/* Uncomment (and remove this text!) to get bold-faced definition list terms
dl.docutils dt {
  font-weight: bold }
*/

div.abstract {
  margin: 2em 5em }

div.abstract p.topic-title {
  font-weight: bold ;
  text-align: center }

div.admonition, div.attention, div.caution, div.danger, div.error,
div.hint, div.important, div.note, div.tip, div.warning {
  margin: 2em ;
  border: medium outset ;
  padding: 1em }

div.admonition p.admonition-title, div.hint p.admonition-title,
div.important p.admonition-title, div.note p.admonition-title,
div.tip p.admonition-title {
  font-weight: bold ;
  font-family: sans-serif }

div.attention p.admonition-title, div.caution p.admonition-title,
div.danger p.admonition-title, div.error p.admonition-title,
div.warning p.admonition-title, .code .error {
  color: red ;
  font-weight: bold ;
  font-family: sans-serif }

/* Uncomment (and remove this text!) to get reduced vertical space in
   compound paragraphs.
div.compound .compound-first, div.compound .compound-middle {
  margin-bottom: 0.5em }

div.compound .compound-last, div.compound .compound-middle {
  margin-top: 0.5em }
*/

div.dedication {
  margin: 2em 5em ;
  text-align: center ;
  font-style: italic }

div.dedication p.topic-title {
  font-weight: bold ;
  font-style: normal }

div.figure {
  margin-left: 2em ;
  margin-right: 2em }

div.footer, div.header {
  clear: both;
  font-size: smaller }

div.line-block {
  display: block ;
  margin-top: 1em ;
  margin-bottom: 1em }

div.line-block div.line-block {
  margin-top: 0 ;
  margin-bottom: 0 ;
  margin-left: 1.5em }

div.sidebar {
  margin: 0 0 0.5em 1em ;
  border: medium outset ;
  padding: 1em ;
  background-color: #ffffee ;
  width: 40% ;
  float: right ;
  clear: right }

div.sidebar p.rubric {
  font-family: sans-serif ;
  font-size: medium }

div.system-messages {
  margin: 5em }

div.system-messages h1 {
  color: red }

div.system-message {
  border: medium outset ;
  padding: 1em }

div.system-message p.system-message-title {
  color: red ;
  font-weight: bold }

div.topic {
  margin: 2em }

h1.section-subtitle, h2.section-subtitle, h3.section-subtitle,
h4.section-subtitle, h5.section-subtitle, h6.section-subtitle {
  margin-top: 0.4em }

h1.title {
  text-align: center }

h2.subtitle {
  text-align: center }

hr.docutils {
  width: 75% }

img.align-left, .figure.align-left, object.align-left, table.align-left {
  clear: left ;
  float: left ;
  margin-right: 1em }

img.align-right, .figure.align-right, object.align-right, table.align-right {
  clear: right ;
  float: right ;
  margin-left: 1em }

img.align-center, .figure.align-center, object.align-center {
  display: block;
  margin-left: auto;
  margin-right: auto;
}

table.align-center {
  margin-left: auto;
  margin-right: auto;
}

.align-left {
  text-align: left }

.align-center {
  clear: both ;
  text-align: center }

.align-right {
  text-align: right }

/* reset inner alignment in figures */
div.align-right {
  text-align: inherit }

/* div.align-center * { */
/*   text-align: left } */

.align-top    {
  vertical-align: top }

.align-middle {
  vertical-align: middle }

.align-bottom {
  vertical-align: bottom }

ol.simple, ul.simple {
  margin-bottom: 1em }

ol.arabic {
  list-style: decimal }

ol.loweralpha {
  list-style: lower-alpha }

ol.upperalpha {
  list-style: upper-alpha }

ol.lowerroman {
  list-style: lower-roman }

ol.upperroman {
  list-style: upper-roman }

p.attribution {
  text-align: right ;
  margin-left: 50% }

p.caption {
  font-style: italic }

p.credits {
  font-style: italic ;
  font-size: smaller }

p.label {
  white-space: nowrap }

p.rubric {
  font-weight: bold ;
  font-size: larger ;
  color: maroon ;
  text-align: center }

p.sidebar-title {
  font-family: sans-serif ;
  font-weight: bold ;
  font-size: larger }

p.sidebar-subtitle {
  font-family: sans-serif ;
  font-weight: bold }

p.topic-title {
  font-weight: bold }

pre.address {
  margin-bottom: 0 ;
  margin-top: 0 ;
  font: inherit }

pre.literal-block, pre.doctest-block, pre.math, pre.code {
  margin-left: 2em ;
  margin-right: 2em }

pre.code .ln { color: gray; } /* line numbers */
pre.code, code { background-color: #eeeeee }
pre.code .comment, code .comment { color: #5C6576 }
pre.code .keyword, code .keyword { color: #3B0D06; font-weight: bold }
pre.code .literal.string, code .literal.string { color: #0C5404 }
pre.code .name.builtin, code .name.builtin { color: #352B84 }
pre.code .deleted, code .deleted { background-color: #DEB0A1}
pre.code .inserted, code .inserted { background-color: #A3D289}

span.classifier {
  font-family: sans-serif ;
  font-style: oblique }

span.classifier-delimiter {
  font-family: sans-serif ;
  font-weight: bold }

span.interpreted {
  font-family: sans-serif }

span.option {
  white-space: nowrap }

span.pre {
  white-space: pre }

span.problematic, pre.problematic {
  color: red }

span.section-subtitle {
  /* font-size relative to parent (h1..h6 element) */
  font-size: 80% }

table.citation {
  border-left: solid 1px gray;
  margin-left: 1px }

table.docinfo {
  margin: 2em 4em }

table.docutils {
  margin-top: 0.5em ;
  margin-bottom: 0.5em }

table.footnote {
  border-left: solid 1px black;
  margin-left: 1px }

table.docutils td, table.docutils th,
table.docinfo td, table.docinfo th {
  padding-left: 0.5em ;
  padding-right: 0.5em ;
  vertical-align: top }

table.docutils th.field-name, table.docinfo th.docinfo-name {
  font-weight: bold ;
  text-align: left ;
  white-space: nowrap ;
  padding-left: 0 }

/* "booktabs" style (no vertical lines) */
table.docutils.booktabs {
  border: 0px;
  border-top: 2px solid;
  border-bottom: 2px solid;
  border-collapse: collapse;
}
table.docutils.booktabs * {
  border: 0px;
}
table.docutils.booktabs th {
  border-bottom: thin solid;
  text-align: left;
}

h1 tt.docutils, h2 tt.docutils, h3 tt.docutils,
h4 tt.docutils, h5 tt.docutils, h6 tt.docutils {
  font-size: 100% }

ul.auto-toc {
  list-style-type: none }

</style>
</head>
<body>
<div class="document">


<a class="reference external image-reference" href="https://odoo-community.org/get-involved?utm_source=readme">
<img alt="Odoo Community Association" src="https://odoo-community.org/readme-banner-image" />
</a>
<div class="section" id="iot-templates">
<h1>IoT Templates</h1>
<!-- !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! This file is generated by oca-gen-addon-readme !!
!! changes will be overwritten.                   !!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! source digest: sha256:cc10ee6af01c555bf9e61159d3aee870da62181fded78e55748ca1abc545d10b
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! -->
<p><a class="reference external image-reference" href="https://odoo-community.org/page/development-status"><img alt="Beta" src="https://img.shields.io/badge/maturity-Beta-yellow.png" /></a> <a class="reference external image-reference" href="http://www.gnu.org/licenses/agpl-3.0-standalone.html"><img alt="License: AGPL-3" src="https://img.shields.io/badge/license-AGPL--3-blue.png" /></a> <a class="reference external image-reference" href="https://github.com/OCA/iot/tree/18.0/iot_template_oca"><img alt="OCA/iot" src="https://img.shields.io/badge/github-OCA%2Fiot-lightgray.png?logo=github" /></a> <a class="reference external image-reference" href="https://translation.odoo-community.org/projects/iot-18-0/iot-18-0-iot_template_oca"><img alt="Translate me on Weblate" src="https://img.shields.io/badge/weblate-Translate%20me-F47D42.png" /></a> <a class="reference external image-reference" href="https://runboat.odoo-community.org/builds?repo=OCA/iot&amp;target_branch=18.0"><img alt="Try me on Runboat" src="https://img.shields.io/badge/runboat-Try%20me-875A7B.png" /></a></p>
<p>Create a system of templates for IoT devices.</p>
<p>When we are using a template we can configure a device with a simple URL
configuration. The device will contact odoo and send the template name.
Odoo will create the device and respond with all the expected data.</p>
<p><strong>Table of contents</strong></p>
<div class="contents local topic" id="contents">
<ul class="simple">
<li><a class="reference internal" href="#usage" id="toc-entry-1">Usage</a></li>
<li><a class="reference internal" href="#bug-tracker" id="toc-entry-2">Bug Tracker</a></li>
<li><a class="reference internal" href="#credits" id="toc-entry-3">Credits</a><ul>
<li><a class="reference internal" href="#authors" id="toc-entry-4">Authors</a></li>
<li><a class="reference internal" href="#contributors" id="toc-entry-5">Contributors</a></li>
<li><a class="reference internal" href="#maintainers" id="toc-entry-6">Maintainers</a></li>
</ul>
</li>
</ul>
</div>
<div class="section" id="usage">
<h2><a class="toc-backref" href="#toc-entry-1">Usage</a></h2>
<ol class="arabic simple">
<li>Create a template with a module or in Iot &gt; Templates</li>
<li>Access Iot &gt; Config Device</li>
<li>Confirm that you want to configurate a new device</li>
<li>Copy the URL</li>
<li>Access the device and send it the configuration url</li>
<li>The device will contact odoo and automatically configure itself.</li>
</ol>
</div>
<div class="section" id="bug-tracker">
<h2><a class="toc-backref" href="#toc-entry-2">Bug Tracker</a></h2>
<p>Bugs are tracked on <a class="reference external" href="https://github.com/OCA/iot/issues">GitHub Issues</a>.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
<a class="reference external" href="https://github.com/OCA/iot/issues/new?body=module:%20iot_template_oca%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**">feedback</a>.</p>
<p>Do not contact contributors directly about support or help with technical issues.</p>
</div>
<div class="section" id="credits">
<h2><a class="toc-backref" href="#toc-entry-3">Credits</a></h2>
<div class="section" id="authors">
<h3><a class="toc-backref" href="#toc-entry-4">Authors</a></h3>
<ul class="simple">
<li>Creu Blanca</li>
</ul>
</div>
<div class="section" id="contributors">
<h3><a class="toc-backref" href="#toc-entry-5">Contributors</a></h3>
<ul class="simple">
<li>Enric Tobella &lt;<a class="reference external" href="mailto:etobella&#64;creublanca.es">etobella&#64;creublanca.es</a>&gt;</li>
</ul>
</div>
<div class="section" id="maintainers">
<h3><a class="toc-backref" href="#toc-entry-6">Maintainers</a></h3>
<p>This module is maintained by the OCA.</p>
<a class="reference external image-reference" href="https://odoo-community.org">
<img alt="Odoo Community Association" src="https://odoo-community.org/logo.png" />
</a>
<p>OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.</p>
<p>This module is part of the <a class="reference external" href="https://github.com/OCA/iot/tree/18.0/iot_template_oca">OCA/iot</a> project on GitHub.</p>
<p>You are welcome to contribute. To learn how please visit <a class="reference external" href="https://odoo-community.org/page/Contribute">https://odoo-community.org/page/Contribute</a>.</p>
</div>
</div>
</div>
</div>
</body>
</html>

```

### File: `iot_template_oca/tests/__init__.py`
```python
from . import test_iot_template

```

### File: `iot_template_oca/tests/test_iot_template.py`
```python
# Copyright 2020 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests.common import HttpCase


class TestIotTemplate(HttpCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))
        self.system = self.env["iot.communication.system"].create({"name": "Testing"})
        self.system_2 = self.env["iot.communication.system"].create(
            {"name": "Testing 2"}
        )
        self.parent_template = self.env["iot.template"].create(
            {
                "name": "Parent template",
                "key_ids": [(0, 0, {"key": "passphrase"})],
                "input_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "INPUT 1",
                            "call_model_id": False,
                            "call_function": "iot_ras_default_action",
                            "params": "{'serial': '${serial}', "
                            "'passphrase': '${passphrase}'}",
                        },
                    )
                ],
                "output_ids": [
                    (
                        0,
                        0,
                        {"name": "OUTPUT 1", "communication_system_id": self.system.id},
                    )
                ],
            }
        )
        self.template = self.env["iot.template"].create(
            {
                "name": "template",
                "parent_id": self.parent_template.id,
                "key_ids": [(0, 0, {"key": "serial2"})],
                "input_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "INPUT 2",
                            "call_model_id": False,
                            "call_function": "iot_ras_default_action",
                            "params": "{'serial': '${serial2}', "
                            "'passphrase': '${passphrase}'}",
                        },
                    )
                ],
                "output_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "OUTPUT 2",
                            "communication_system_id": self.system_2.id,
                            "params": "{'ip': '1234'}",
                        },
                    )
                ],
            }
        )

    def _get_wizard(self):
        wizard = self.env["iot.device.configure"].create({})
        self.assertTrue(wizard.serial)
        self.assertTrue(wizard.url)
        return wizard

    def test_generation(self):
        wizard = self._get_wizard()
        device_config = self.url_open(
            wizard.url, data={"template": self.template.name}
        ).json()
        device = self.env["iot.device"].search([("name", "=", device_config["name"])])
        self.assertTrue(device)
        self.assertEqual(1, len(device))
        self.assertEqual(2, len(device.output_ids))
        self.assertEqual(2, len(device.input_ids))
        input1 = device.input_ids.filtered(
            lambda r: r.template_input_id == self.parent_template.input_ids
        )
        self.assertTrue(input1)
        input2 = device.input_ids.filtered(
            lambda r: r.template_input_id == self.template.input_ids
        )
        self.assertTrue(input2)
        self.assertNotEqual(input1, input2)
        self.assertGreater(len(input1.passphrase), 0)
        self.assertGreater(len(input2.passphrase), 0)
        self.assertEqual(input1.passphrase, input2.passphrase)
        self.assertGreater(len(input1.serial), 0)
        self.assertGreater(len(input2.serial), 0)
        self.assertNotEqual(input1.serial, input2.serial)
        output1 = device.output_ids.filtered(
            lambda r: r.template_output_id == self.parent_template.output_ids
        )
        self.assertTrue(output1)
        output2 = device.output_ids.filtered(
            lambda r: r.template_output_id == self.template.output_ids
        )
        self.assertTrue(output2)
        self.assertNotEqual(output1, output2)
        self.assertEqual(output1.communication_system_id, self.system)
        self.assertFalse(output1.ip)
        self.assertEqual(output2.communication_system_id, self.system_2)
        self.assertEqual(output2.ip, "1234")

    def test_missing_configuration(self):
        wizard = self._get_wizard()
        url = wizard.url.replace(wizard.serial, wizard.serial + wizard.serial)
        device_config = self.url_open(url, data={"template": self.template.name}).json()
        self.assertFalse(device_config)

    def test_no_double_configuration(self):
        """
        We expect that it is not allowed to do the same call twice,
        the first it must work properly.
        No result should be returned on the second one
        """
        wizard = self._get_wizard()
        url = wizard.url
        device_config = self.url_open(url, data={"template": self.template.name}).json()
        self.assertTrue(device_config)
        device = self.env["iot.device"].search([("name", "=", device_config["name"])])
        self.assertTrue(device)
        device_config = self.url_open(url, data={"template": self.template.name}).json()
        self.assertFalse(device_config)

    def test_constrain_hierarchy(self):
        with self.assertRaises(UserError):
            self.parent_template.parent_id = self.template

```

### File: `iot_template_oca/views/iot_template_views.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <record id="iot_template_form" model="ir.ui.view">
        <field name="name">iot.template.form</field>
        <field name="model">iot.template</field>
        <field name="arch" type="xml">
            <form create="0">
                <header />
                <sheet>
                    <div class="oe_button_box" name="button_box" />
                    <field
                        name="image_1920"
                        widget='image'
                        class="oe_avatar"
                        options='{"preview_image": "image_128"}'
                    />
                    <div class="oe_title">
                        <h1>
                            <field name="name" />
                        </h1>
                    </div>
                    <group>
                        <field name="group_id" />
                        <field name="icon" />
                        <field
                            name="tag_ids"
                            widget="many2many_tags"
                            options="{'color_field': 'color'}"
                        />
                    </group>
                    <notebook>
                        <page string="Keys" id="key">
                            <field name="key_ids">
                                <list editable="bottom">
                                    <field name="key" />
                                </list>
                                <form>
                                    <sheet>
                                        <group>
                                            <field name="key" />
                                        </group>
                                    </sheet>
                                </form>
                            </field>
                        </page>
                        <page string="Inputs" id="input">
                            <field name="input_ids">
                                <list>
                                    <field name="name" />
                                    <field name="call_model_id" />
                                    <field name="call_function" />
                                </list>
                                <form>
                                    <sheet>
                                        <group>
                                            <field name="name" />
                                            <field name="call_model_id" />
                                            <field name="call_function" />
                                            <field name="params" />
                                        </group>
                                    </sheet>
                                </form>
                            </field>
                        </page>
                        <page string="Outputs" id="output">
                            <field name="output_ids">
                                <list>
                                    <field name="name" />
                                    <field name="communication_system_id" />
                                </list>
                                <form>
                                    <sheet>
                                        <group>
                                            <field name="name" />
                                            <field name="communication_system_id" />
                                            <field name="params" />
                                        </group>
                                    </sheet>
                                </form>
                            </field>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>
    <record id="iot_template_list" model="ir.ui.view">
        <field name="name">iot.template.form</field>
        <field name="model">iot.template</field>
        <field name="arch" type="xml">
            <list>
                <field name="name" />
            </list>
        </field>
    </record>
    <record model="ir.actions.act_window" id="iot_template_action">
        <field name="name">IoT Templates</field>
        <field name="type">ir.actions.act_window</field>
        <field name="res_model">iot.template</field>
        <field name="view_mode">list,form</field>
    </record>
    <menuitem
        name="Templates"
        sequence="90"
        id="iot_template_menu"
        action="iot_template_action"
        parent="iot_oca.iot_configuration_menu"
    />
</odoo>

```

### File: `iot_template_oca/wizards/__init__.py`
```python
from . import iot_device_configure

```

### File: `iot_template_oca/wizards/iot_device_configure.py`
```python
# Copyright 2020 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from uuid import uuid4

from odoo import api, fields, models


class IotDeviceConfigure(models.TransientModel):
    _name = "iot.device.configure"
    _description = "Configure a IoT device"

    serial = fields.Char(readonly=True, required=True, default=lambda r: uuid4())
    url = fields.Char(compute="_compute_url")

    @api.depends("serial")
    def _compute_url(self):
        for record in self:
            record.url = (
                self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                + "/iot/"
                + record.serial
                + "/configure"
            )

    @api.model
    def configure(self, serial, template_id, ip=False, **kwargs):
        config = self.search([("serial", "=", serial)])
        if not config:
            return {}
        config.unlink()
        device = self.env["iot.device"].create({"name": serial, "ip": ip})
        template = self.env["iot.template"].search([("name", "=", template_id)])
        if template:
            template.apply_template(device, template._get_keys(serial))
        return device.get_iot_configuration()

```

### File: `iot_template_oca/wizards/iot_device_configure.xml`
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!--
    Copyright 2017 Eficent Business and IT Consulting Services, S.L.
    Copyright 2017 Creu Blanca
    License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
-->
<odoo>
    <record model="ir.ui.view" id="configure_form">
        <field name="name">iot.device.configure</field>
        <field name="model">iot.device.configure</field>
        <field name="type">form</field>
        <field name="arch" type="xml">
            <form string="Apply template">
                <div>
                    Use this URL on your device configuration
                </div>
                <group>
                    <field
                        name="url"
                        widget="CopyClipboardChar"
                        label="Configuration URL"
                    />
                </group>
                <footer>
                    <button string="Close" class="btn-default" special="cancel" />
                </footer>
            </form>
        </field>
    </record>
    <record id="configure_action" model="ir.actions.server">
        <field name="name">Apply Template</field>
        <field name="model_id" ref="model_iot_device_configure" />
        <field name="state">code</field>
        <field name="code">action = model.create({}).get_formview_action()
action["target"] = "new"</field>
    </record>
    <menuitem
        name="Add a new Device"
        sequence="1"
        id="iot_device_configuration_menu"
        action="configure_action"
        parent="iot_oca.iot_configuration_menu"
        groups="iot_oca.group_iot_manager"
    />
</odoo>

```

