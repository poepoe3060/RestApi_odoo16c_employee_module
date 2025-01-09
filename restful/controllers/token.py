# Part of odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
import werkzeug.wrappers
from odoo import http
from odoo.addons.restful.common import invalid_response, valid_response, STATUS_CODES
from odoo.http import request
from odoo.exceptions import AccessError, AccessDenied
from odoo.addons.web.controllers.main import ensure_db
import copy
from odoo.http import Response
from odoo.addons.restful.controllers.main import (
    validate_token,
    public_validate_token
)

_logger = logging.getLogger(__name__)

expires_in = "restful.access_token_expires_in"


class AccessToken(http.Controller):
    """."""

    def __init__(self):

        self._token = request.env["api.access_token"]
        self._expires_in = request.env.ref(expires_in).sudo().value

    @http.route("/api/auth/token", methods=["GET"], type="http", auth="none", csrf=False)
    def token(self, **post):
        ensure_db()
        _token = request.env["api.access_token"]
        params = ["db", "login", "password"]
        params = {key: post.get(key) for key in params if post.get(key)}
        db, username, password = (
            "",
            "",
            "",
        )
        _credentials_includes_in_body = all([db, username, password])
        if not _credentials_includes_in_body:
            # The request post body is empty the credetials maybe passed via the headers.
            headers = request.httprequest.headers
            db = request.session.db
            username = headers.get("login")
            if headers.get("login"):
                # user = request.env["res.users"].sudo().search(
                #     ['|', ('login', '=', headers.get("login")), ('mobile', '=', headers.get("login"))])
                user = request.env["res.users"].sudo().search(
                    [('login', '=', headers.get("login"))])
                if user:
                    if user.is_approved_user == 'draft':
                        data = {
                            "status": "fail",
                            # "error": "You need to be approve by admin."
                            "message": "Please wait for admin’s approval"
                        }
                        return valid_response(data)
                    elif not user.otp_confirm:
                        data = {"status": "fail", "error": "Need to verify your OTP.", "type": "need_to_verify_otp"}
                        return valid_response(data)
                        # response = {**copy.deepcopy(STATUS_CODES.get(400)), **data}
                        # return werkzeug.wrappers.Response(
                        #     content_type="application/json; charset=utf-8",
                        #     headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                        #     response=json.dumps(response)
                        # )
                    username = user.login
                else:
                    data = {"status": "fail", "error": "Email or Password is Incorrect."}
                    return valid_response(data)
                    # response = {**copy.deepcopy(STATUS_CODES.get(400)), **data}
                    # return werkzeug.wrappers.Response(
                    #     content_type="application/json; charset=utf-8",
                    #     headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
                    #     response=json.dumps(response)
                    # )

            password = headers.get("password")
            _credentials_includes_in_headers = all([db, username, password])
            if not _credentials_includes_in_headers:
                # Empty 'db' or 'username' or 'password:
                return invalid_response(
                    "missing error", "either of the following are missing [db, username,password]", 403,
                )
        # Login in odoo database:
        try:
            request.session.authenticate(db, username, password)
        except AccessError as aee:
            return invalid_response("Access error", "Error: %s" % aee.name)
        except AccessDenied as ade:
            data = {"status": "fail", "error": "Email or Password is Incorrect."}
            return valid_response(data)

            # response = {**copy.deepcopy(STATUS_CODES.get(400)), **data}
            # return Response(
            #     content_type="application/json; charset=utf-8",
            #     headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            #     response=json.dumps(response)
            # )

        except Exception as e:
            # Invalid database:
            info = "The database name is not valid {}".format((e))
            error = "invalid_database"
            _logger.error(info)
            return invalid_response("wrong database name", error, 403)

        uid = request.session.uid
        # odoo login failed:
        if not uid:
            info = "authentication failed"
            error = "authentication failed"
            _logger.error(info)
            return invalid_response(401, error, info)

        # Generate tokens
        result = []
        access_token = _token.find_one_or_create_token(user_id=uid, create=True)
        if access_token:
            if headers.get("app-id"):
                app_id = headers.get("app-id")
                userModel = request.env["res.users"].sudo().search(
                    ['|', ('login', '=', headers.get("login")), ('mobile', '=', headers.get("login"))])
                # print("User",userModel,"ID",app_id)
                userModel.write({
                    "mobile_token": app_id
                })
            access_token_result = request.env["api.access_token"].sudo().search([("user_id", "=", uid)],
                                                                                order="id DESC",
                                                                                limit=1)
            result.append({
                "token": access_token,
                "expire_at": str(access_token_result.expires)
            })
        # Successful response:
        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(
                {
                    "user_id": uid,
                    "access_token": result,
                    "expires_in": request.env.ref(expires_in).sudo().value
                }
            ),
        )

    @validate_token
    @http.route(["/api/auth/token"], methods=["DELETE"], type="http", auth="none", csrf=False)
    def delete(self, **post):
        """Delete a given token"""

        _token = request.env["api.access_token"]
        token1 = None
        headers = request.httprequest.headers
        if headers.get("access-token"):
            token1 = headers.get("access-token")

        access_token = request.httprequest.headers.get(""
                                                       "")

        access_token = _token.search([("token", "=", token1)], limit=1)
        if not access_token:
            status = {
                "status": "fail",
                "message": "access token is expired or invalid"
            }

            return valid_response(status)
        for token in access_token:
            token.unlink()
        # Successful response:
        status = {
            "status": "success"
        }
        return valid_response(status)
