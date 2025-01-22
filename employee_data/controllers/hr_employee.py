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
    @http.route("/api/employee-lists", type="http", auth="none", methods=["GET"], csrf=False)
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
                'mobile_phone': rec.mobile_phone,
                'department': {
                    'id': rec.department_id.id,
                    'name': rec.department_id.name
                },
            })
        start_index = (int(page_no) - 1) * int(per_page)
        end_index = start_index + int(per_page)
        response_values['result'] = values[start_index:end_index]
        return valid_response(response_values)

    @validate_token
    @http.route("/api/employee-lists/<id>", type="http", auth="none", methods=["GET"], csrf=False)
    def get_dedicated_employee_detail(self, id=None):
        """
        return employee detail
        """
        try:
            id = int(id)
        except ValueError:
            return valid_response({"status": "fail", "message": "Id must be an integer"})

        detail = request.env['hr.employee'].sudo().browse(int(id))
        if not detail:
            return valid_response({"status": "fail", "message": "Employee is not found!"})

        data = {
                'id': detail.id,
                'name': detail.name,
                'mobile_phone': detail.mobile_phone,
                'work_phone': detail.work_phone,
                'work_email': detail.work_email,
                'work_address': {
                    'id': detail.address_id.id,
                    'name': detail.address_id.name
                },
                'department': {
                    'id': detail.department_id.id,
                    'name': detail.department_id.name
                },
                'manager': {
                    'id': detail.parent_id.id,
                    'name': detail.parent_id.name
                },
                'marital': detail.marital,
            }

        return valid_response(data)
