import requests
import json
from odoo import http
from odoo.http import request
from odoo.addons.restful.common import (
    valid_response,
)
from odoo.addons.restful.controllers.main import (
    validate_token
)


class CustomPRoductAPIController(http.Controller):
    @validate_token
    @http.route("/api/warehouse/location", type="http", auth="none", methods=["GET"], csrf=False)
    def get_warehouse_list(self):
        ICPSudo = request.env['ir.config_parameter'].sudo()
        main_warehouse_location_id = ICPSudo.get_param('inherit_models.main_warehouse_location_id')

        user_id = request.env.user.id
        location_ids = request.env['res.users'].sudo().search(
            [('id', '=', int(user_id))]).partner_id.user_group_id.location_ids.ids
        list = []
        warehouse_list = request.env['stock.location'].sudo().search(
            [("usage", "=", "internal"), ("id", "in", location_ids)])
        if not warehouse_list:
            return valid_response({})
        for warehouse in warehouse_list:
            s_data = {
                'id': warehouse.id,
                'name': warehouse.name,
                'code': warehouse.barcode,
                'short_name': warehouse.location_id.name,
                'full_name': warehouse.location_id.name + "/" + warehouse.name,
                'main_warehouse_location': True if warehouse.id == int(main_warehouse_location_id) else False,
            }
            list.append(s_data)
        return valid_response(list)
