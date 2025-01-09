from datetime import date,datetime
from odoo import http
from odoo.http import request
from odoo.addons.restful.common import (
    valid_response,
)
from odoo.addons.restful.controllers.main import (
    validate_token
)


class LoadingEmployee(http.Controller):
    @validate_token
    @http.route("/api/employee-list", type="http", auth="none", methods=["GET"], csrf=False)
    def get_employee_list(self,page_no=None, per_page=None):
        """
        return list of employee
        """
        if not page_no:
            page_no = 1
        if not per_page:
            per_page = 5

        employee = request.env['hr.employee'].sudo().search([],order="id asc")
        response_values = {}
        values = []
        for rec in employee:
            values.append({
                'id': rec.id,
                'name': rec.name,
                'mobile_phone': rec.mobile_phone
            })
        start_index = (int(page_no) - 1) * int(per_page)
        end_index = start_index + int(per_page)
        response_values['result'] = values[start_index:end_index]
        return valid_response(response_values)
