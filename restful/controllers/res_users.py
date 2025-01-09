import random
import logging
import json
import uuid

import requests
import io
from datetime import datetime, timedelta, date
from odoo import http, SUPERUSER_ID
from odoo.http import request, Request, JsonRPCDispatcher
from odoo.exceptions import AccessDenied
from odoo.modules.registry import Registry
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED
# from odoo.addons.static_data.models.notification import BusinessNotification
from odoo.addons.restful.controllers.main import (
    validate_token
)
import werkzeug.wrappers
import base64
from odoo.addons.restful.common import (
    extract_arguments,
    invalid_response,
    valid_response,
    alternative_json_response,
    send_sms
)
import re
from odoo.addons.web.controllers.main import ensure_db
from odoo.http import request, Response
from odoo.service.common import exp_login
from odoo.tools import date_utils
import threading, odoo

expires_in = "restful.access_token_expires_in"
_logger = logging.getLogger(__name__)


class ResUsersAPIController(http.Controller):

    def __init__(self):
        self._token = request.env["api.access_token"]
        self._expires_in = request.env.ref(expires_in).sudo().value

    def generate_six_digit_code(self):
        code = ""
        for x in range(6):
            code = code + str(random.randint(0, 9))
        return code

    @http.route("/api/user/signup", methods=["POST"], type="json", auth="none", csrf=False, custom_response=True)
    def create_user(self):

        ensure_db()
        user_val = {}
        partner_val = {}
        ICPSudo = request.env['ir.config_parameter'].sudo()
        otp_life_time = ICPSudo.get_param('inherit_models.otp_life_time')
        data = request.httprequest.data
        jsondata = json.loads(data)
        user_type_id = 1

        if jsondata:
            # User Values
            sixdigit = self.generate_six_digit_code()
            user_val["otp"] = sixdigit
            user_val["otp_send_date"] = date.today()
            user_val["otp_send_count"] = 1
            user_val["otp_expiry_time"] = datetime.now() + timedelta(seconds=int(otp_life_time))
            print(">>>>>>>", jsondata.get("company"))
            if not jsondata.get("name"):
                return {"status": "fail", "message": "Name field is required."}
            if not jsondata.get("mobile"):
                return {"status": "fail", "message": "Mobile Phone field is required."}
            if not jsondata.get("email"):
                return {"status": "fail", "message": "Email field is required."}
            if not jsondata.get("password"):
                return {"status": "fail", "message": "Password field is required."}
            if jsondata.get("password") and re.search(r'[\s]', jsondata.get("password")):
                return {"status": "fail", "message": "Invalid password format."}
            user_val["name"] = jsondata.get("name") if jsondata.get("name") else jsondata.get("mobile")
            if jsondata.get("email"):
                check_email = request.env["res.users"].sudo().search(
                    [('login', '=', jsondata.get("email"))])
                if check_email:
                    return {"status": "fail",
                            "message": "This user is already registered. please use another email."}
            user_val["login"] = jsondata.get("email")
            user_val["mobile"] = jsondata.get("mobile")
            user_val["password"] = jsondata.get("password")
            user_val["from_api"] = True
            user_val["mobile_token"] = jsondata.get("app-id")
            user_val["sel_groups_1_9_10"] = 9

            # for b2c and b2b
            domain = []

            # if jsondata.get("user_type_id"):
            #     domain.append(('id', "=", int(jsondata.get("user_type_id"))))
            # else:
            #     domain.append(('code', "=", 'b2c'))
            # usertype = request.env["res.users.type"].sudo().search(domain,
            #                                                        limit=1)
            #
            # if usertype:
            #     if not usertype.need_approved:
            user_val["is_approved_user"] = 'approved'
            # user_type_id = usertype.id

        # Try create new object
        db_name = request.session.db
        registry = Registry(db_name)
        cr = registry.cursor()
        cr._cnx.set_isolation_level(ISOLATION_LEVEL_READ_COMMITTED)
        Model = request.env(cr, SUPERUSER_ID)["res.users"]
        try:
            new_id = Model.create(user_val)
        except Exception as identifier:
            return identifier

        # Partner Values
        partner = new_id.partner_id
        country_model = request.env["res.country"]
        default_country = country_model.sudo().search([("code", "=", "MM")])
        if partner:
            partner_val["email"] = jsondata.get("email")
            partner_val["country_id"] = default_country.id if default_country else False
            partner_val["street"] = jsondata.get("street")
            partner_val["street2"] = jsondata.get("street2")
            partner_val["zip"] = jsondata.get("zip")
            partner_val["state_id"] = jsondata.get("state_id")
            partner_val["dob"] = jsondata.get("dob")
            if jsondata.get("country_id"):
                chk_country_id = request.env['res.country'].sudo().search(
                    [('id', '=', int(jsondata.get("country_id")))])
                if chk_country_id:
                    partner_val["country_id"] = jsondata.get("country_id")
                else:
                    return {"status": "fail", "error": "country id is invalid."}
            if jsondata.get("state_id"):
                chk_country_state = request.env['res.country.state'].sudo().search(
                    [('id', '=', int(jsondata.get("state_id")))])
                if chk_country_state:
                    partner_val["state_id"] = jsondata.get("state_id")
                else:
                    return {"status": "fail", "error": "state/division id is invalid."}
            if jsondata.get("township_id"):
                chk_township = request.env['res.township'].sudo().search(
                    [('id', '=', int(jsondata.get("township_id")))])
                if chk_township:
                    partner_val["township_id"] = jsondata.get("township_id")
                else:
                    return {"status": "fail", "error": "township id is invalid"}

            partner_val["customer_rank"] = 1

            partner_val["city"] = jsondata.get("city")
            # partner_val["company"] = jsondata.get("company")
            partner.sudo().write(partner_val)

        cr.commit()
        cr.close()
        ####------------->
        # Here Have to send sms

        ICPSudo = request.env['ir.config_parameter'].sudo()
        otp_life_time = ICPSudo.get_param('inherit_models.otp_life_time')
        # seller_name = ICPSudo.get_param('inherit_models.seller_name')
        # sms = ICPSudo.get_param('inherit_models.sms_otp_format')
        # sms = sms.replace("{otp}", sixdigit)
        # sms = sms.replace("{min}", otp_life_time)
        # status_code = send_sms(self, jsondata["mobile"], sms)
        user = new_id
        otp_life_time_min = int(int(otp_life_time) / 60)
        placeholders = [{'otp': sixdigit, 'min': otp_life_time_min}]
        threaded_calculation = threading.Thread(
            target=request.env['sent.notification'].sent_all_notifications, args=(['otp', user, placeholders]))
        threaded_calculation.start()
        ####------------->
        return {"status": "success", "otp_life_in_sec": int(otp_life_time)}

    @http.route("/api/user/verify", methods=["POST"], type="json", auth="none", csrf=False, custom_response=True)
    def _otp_verify(self):

        data = request.httprequest.data
        jsondata = json.loads(data)
        if not jsondata.get('login'):
            return {"status": "fail", "message": "login is required."}
        if not jsondata.get('otp'):
            return {"status": "fail", "message": "otp is required."}
        login = jsondata.get("login")
        otp = jsondata.get("otp")
        UserModel = request.env["res.users"].sudo()
        response_val = {}
        if login:
            # user = UserModel.search(['|', ('login', '=', mobile), ("mobile", "=", mobile)])
            user = UserModel.search([('login', '=', login)])
            if user and user.otp == otp:
                if datetime.now() > user.otp_expiry_time:
                    response_val = {"status": "fail", "error": "otp has expired."}
                    return response_val

                if not user.otp_confirm:
                    threaded_calculation = threading.Thread(
                        target=request.env['sent.notification'].sent_all_notifications,
                        args=(['register_success', user, None]))
                    threaded_calculation.start()
                    # sent noti
                    # BusinessNotification.save_notification("Registration Successful.",
                    #                                        "Thank you for registering with us.", user)
                    #
                    # ICPSudo = request.env['ir.config_parameter'].sudo()
                    # sms = ICPSudo.get_param('inherit_models.register_success_text')
                    # status_code = send_sms(self, jsondata["mobile"], sms)

                # else:
                # sent noti
                # BusinessNotification.save_notification("Reset Password Successful.",
                #                                        "Your password have been changed.", user)

                user.write({"otp_confirm": True})
                response_val["status"] = "success"
                response_val["name"] = user.name
                response_val["login"] = user.login

                if user.is_approved_user == 'draft':
                    response_val["code"] = "need_approval"
                    response_val["message"] = "You need to be approve by admin."


            elif user and user.otp != otp:
                response_val = {"status": "fail", "error": "invalid otp number."}
            else:
                response_val = {"status": "fail", "error": "invalid mobile number."}

            return response_val

    # @validate_token
    # @http.route("/api/testing", methods=["POST"], type="http", auth="none", csrf=False)
    # def testing(self, phone=None):
    #     user = request.env.user
    #     threaded_calculation = threading.Thread(
    #         target=request.env['sent.notification'].sent_all_notifications,
    #         args=(['test_email', user, None]))
    #     threaded_calculation.start()
    #     status = []
    #     return valid_response(status)

    @http.route("/api/user/type", methods=["GET"], type="http", auth="none", csrf=False)
    def _mobile_check(self):
        userType = request.env["res.users.type"].sudo().search([("_active", "=", True)])
        data = []
        if userType:
            for user in userType:
                data.append({
                    'id': user.id,
                    'code': user.code,
                    'name': user.name
                })

        return valid_response(data)

    @http.route("/api/user/profile", methods=["POST"], type="http", auth="none", csrf=False)
    def get_user_data(self):
        request._response = alternative_json_response.__get__(request, Request)
        data = request.httprequest.data
        jsondata = json.loads(data)
        mobile = jsondata.get("mobile")
        UserModel = request.env["res.users"].sudo()
        response_val = {}
        c_user = UserModel.search([("login", "=", mobile)])  # c_user === CURRENT USER
        if c_user:
            response_val['name'] = c_user.name
            response_val['mobile'] = c_user.mobile
            response_val['login'] = c_user.login
        else:
            response_val = {"status": "fail", "message": "Invalid mobile number"}
        return response_val

    @http.route("/api/exist/user", methods=["POST"], type="json", auth="none", csrf=False, custom_response=True)
    def check_user_data(self, phone=None):

        ICPSudo = request.env['ir.config_parameter'].sudo()
        otp_life_time = ICPSudo.get_param('inherit_models.otp_life_time')
        otp_limit_count = ICPSudo.get_param('inherit_models.otp_limit_count')
        data = request.httprequest.data
        jsondata = json.loads(data)
        login = jsondata.get("login")
        UserModel = request.env["res.users"].sudo()
        response_val = {}
        c_user = UserModel.search([("login", "=", login)])  # c_user === CURRENT USER

        if c_user:
            if c_user.otp_send_count < int(otp_limit_count) or date.today() != c_user.otp_send_date:
                # response_val['name'] = c_user.name
                # response_val['mobile'] = c_user.mobile
                # response_val['login'] = c_user.login
                # response_val['status'] = 'success'
                response_val = {'exist': True, 'otp_life_in_sec': int(otp_life_time)}
                sixdigit = self.generate_six_digit_code()
                otp_expiry_time = datetime.now() + timedelta(seconds=int(otp_life_time))
                if date.today() == c_user.otp_send_date:
                    update_otp = c_user.write({"otp": sixdigit, "otp_expiry_time": otp_expiry_time,
                                               'otp_send_count': c_user.otp_send_count + 1})
                else:
                    update_otp = c_user.write({"otp": sixdigit, "otp_expiry_time": otp_expiry_time, 'otp_send_count': 1,
                                               "otp_send_date": date.today()})
                if update_otp:
                    ICPSudo = request.env['ir.config_parameter'].sudo()
                    otp_life_time = ICPSudo.get_param('inherit_models.otp_life_time')
                    # seller_name = ICPSudo.get_param('inherit_models.seller_name')
                    # sms = ICPSudo.get_param('inherit_models.sms_otp_format')
                    # sms = sms.replace("{otp}", sixdigit)
                    # sms = sms.replace("{min}", otp_life_time)
                    # status_code = send_sms(self, c_user.login, sms)
                    otp_life_time_min = int(int(otp_life_time) / 60)
                    placeholders = [{'otp': sixdigit, 'min': otp_life_time_min}]
                    threaded_calculation = threading.Thread(
                        target=request.env['sent.notification'].sent_all_notifications,
                        args=(['otp', c_user, placeholders]))
                    threaded_calculation.start()
                    # response_val['otp'] = c_user.otp
                    ####------------->
                    # Here Have to send sms
                    ####------------->
            else:

                response_val = {"status": "fail", "message": "exceeds otp send limit"}
        else:
            response_val = {'exist': False}
        return response_val

    @http.route("/api/user/reset/password", methods=["POST"], type="json", auth="none", csrf=False,
                custom_response=True)
    def user_reset_password(self):

        response_val = {}
        data = request.httprequest.data
        jsondata = json.loads(data)
        login = jsondata.get("login")
        otp = jsondata.get("otp")
        new_password = jsondata.get("password")
        if not new_password:
            return {"status": "fail", "message": "new password is required."}
        if not login:
            return {"status": "fail", "message": "login is required."}
        if not otp:
            return {"status": "fail", "message": "otp is required."}

        UserModel = request.env["res.users"].sudo()
        c_user = UserModel.search([("login", "=", login)])  # c_user === CURRENT USER

        if c_user and c_user.otp == otp:
            reset_password = c_user.write({"password": str(new_password), "otp_confirm": True})
            if reset_password:
                response_val["status"] = "success"
                # response_val["mobile"] = c_user.mobile

                # sent noti
                threaded_calculation = threading.Thread(
                    target=request.env['sent.notification'].sent_all_notifications,
                    args=(['reset_password', c_user, None]))
                threaded_calculation.start()
                # BusinessNotification.save_notification("New password activated.",
                #                                        "Your password is successfully changed.",
                #                                        c_user)

                # sent sms
                # ICPSudo = request.env['ir.config_parameter'].sudo()
                # sms = ICPSudo.get_param('inherit_models.reset_password_success_text')
                # status_code = send_sms(self, mobile, sms)

            else:
                response_val = {"status": "fail", "error": "Reset password Fail."}
        else:
            response_val = {"status": "fail", "error": "invaild otp or login account."}

        return response_val

    @validate_token
    @http.route("/api/password/change", methods=["POST"], type='json', auth="none", csrf=False, custom_response=True)
    def user_change_password(self, **args):

        response_val = {}
        data = request.httprequest.data
        jsondata = json.loads(data)
        new_password = jsondata.get("new_password")
        old_password = jsondata.get("old_password")
        ICPSudo = request.env['ir.config_parameter'].sudo()
        old_password_setting = ICPSudo.get_param('inherit_models.old_password_setting')

        if not new_password:
            return {"status": "fail", "message": "new password is required."}
        UserModel = request.env["res.users"].sudo()
        try:
            c_user = UserModel.search([("id", "=", int(request.uid))])  # c_user === CURRENT USER

            if old_password_setting:
                if old_password:
                    db = request.session.db
                    # check old password
                    uid = exp_login(db, c_user.login, old_password)
                    if uid:
                        change_password = c_user.sudo().write({"password": str(new_password)})
                        if change_password:
                            response_val["status"] = "success"
                            response_val["mobile"] = c_user.mobile
                            # sent noti
                            threaded_calculation = threading.Thread(
                                target=request.env['sent.notification'].sent_all_notifications,
                                args=(['password_change', c_user, None]))
                            threaded_calculation.start()
                            # BusinessNotification.save_notification("New password activated.",
                            #                                        "Your password is successfully changed.",
                            #                                        c_user)
                        else:
                            response_val = {"status": "fail", "message": "Change password Fail."}
                    else:
                        response_val = {"status": "fail", "message": "old password is wrong."}
                else:
                    response_val = {"status": "fail", "message": "old password is required."}
            else:
                if c_user:
                    change_password = c_user.sudo().write({"password": str(new_password)})
                    if change_password:
                        response_val["status"] = "success"
                        response_val["mobile"] = c_user.mobile

                        # sent noti
                        threaded_calculation = threading.Thread(
                            target=request.env['sent.notification'].sent_all_notifications,
                            args=(['password_change', c_user, None]))
                        threaded_calculation.start()
                        # BusinessNotification.save_notification("New password activated.",
                        #                                        "Your password is successfully changed.",
                        #                                        c_user)
                    else:
                        response_val = {"status": "fail", "message": "Change password Fail."}

        except AccessDenied as ade:
            response_val = {"status": "fail", "message": "Incorrect Old Password"}
            return response_val
        return response_val

    """LOGIN WITH FACEBOOK"""

    def check_fb_access(self, user_id, access_token):
        url = "https://graph.facebook.com/me?"
        params = {"access_token": access_token, "fields": ["id", "name"]}
        r = requests.get(url, params=params)
        response = r.json()
        if r.ok:
            if str(user_id) == response["id"]:
                return response
        else:
            return response

    def check_fb_user(self, user_id, access_token):
        # checking fb token
        check_fb_access = self.check_fb_access(user_id, access_token)
        if not check_fb_access.get("error"):
            already = request.env["res.users"].sudo().search([("oauth_uid", "=", user_id)], limit=1)
            # ("oauth_access_token","=",access_token)
            if already:
                if already.oauth_access_token != access_token:
                    already.sudo().write({"oauth_access_token": access_token})
                _token = request.env["api.access_token"]
                access_token = _token.find_one_or_create_token_for_FB_login(user_id=already.id, create=True)
                return {
                    "uid": already.id,
                    "status": "success",
                    "access_token": access_token.token,
                    "expires_in": self._expires_in,
                    "provider": "facebook",
                }
            else:
                return {"uid": False}
        else:
            return check_fb_access

    @http.route("/api/user/login_with_facebook", methods=["POST"], type="json", auth="none", csrf=False,
                custom_response=True)
    def login_with_facebook(self):

        ensure_db()
        user_val = {}
        partner_val = {}
        data = request.httprequest.data
        jsondata = json.loads(data)
        check_fb_user = self.check_fb_user(jsondata.get("oauth_uid"), jsondata.get("oauth_access_token"))
        if check_fb_user.get("error"):
            error = check_fb_user.get("error")
            return {"status": "fail", "message": error.get("message")}
        if not check_fb_user.get("uid"):
            provider = request.env["auth.oauth.provider"]
            _fb = provider.sudo().search([("name", "=", "Facebook Graph")], limit=1)
            user_val["oauth_provider_id"] = _fb.id if _fb else 2
            user_val["oauth_uid"] = jsondata.get("oauth_uid")
            user_val["oauth_access_token"] = jsondata.get("oauth_access_token")
            user_val["login"] = jsondata.get("name")
            user_val["name"] = jsondata.get("name")
            user_val["otp_confirm"] = True
        else:
            return check_fb_user

        # Try create new object
        db_name = request.session.db
        registry = Registry(db_name)
        cr = registry.cursor()
        cr._cnx.set_isolation_level(ISOLATION_LEVEL_READ_COMMITTED)
        Model = request.env(cr, SUPERUSER_ID)["res.users"]
        try:
            new_id = Model.create(user_val)
        except Exception as identifier:
            return identifier

        # Partner Values
        partner = new_id.partner_id
        country_model = request.env["res.country"]
        default_country = country_model.sudo().search([("code", "=", "MM")])
        if partner:
            partner_val["email"] = jsondata.get("email")
            partner_val["country_id"] = default_country.id if default_country else False
            partner_val["city"] = jsondata.get("city")
            partner_val["street"] = jsondata.get("street")
            partner_val["street2"] = jsondata.get("street2")
            partner_val["zip"] = jsondata.get("zip")
            partner_val["state_id"] = jsondata.get("state_id")
            partner.sudo().write(partner_val)

        uid = new_id.id
        # Token Model
        _token = request.env(cr, SUPERUSER_ID)["api.access_token"]
        # Generate tokens
        access_token = _token.find_one_or_create_token_for_FB_login(user_id=uid, create=True)
        cr.commit()
        cr.close()

        # Successful response:
        return {
            "uid": uid,
            "status": "success",
            "access_token": access_token.token,
            "expires_in": self._expires_in,
            "provider": "facebook",
        }

    # Get User Profile
    @validate_token
    @http.route("/api/user", methods=["GET"], type="http", auth="none", csrf=False)
    def get_user_profile(self):

        user_id = request.env.user
        res_partner = request.env['res.users'].sudo().search([('id', '=', int(user_id))])
        print(">>>", res_partner)
        response_val = {}
        country = {}
        state = {}
        township = {}
        # balance = RewardAPIController.calculate_reward_balance(self, res_partner.partner_id.id)
        if res_partner:
            config_obj = request.env['ir.config_parameter'].sudo(
            ).get_param('web.base.url')
            attachment = request.env['ir.attachment'].sudo().search(
                [('res_model', '=', 'res.partner'), ('res_field', '=', 'image_1920'),
                 ('res_id', '=', res_partner.partner_id.id)])
            if attachment:
                partner = request.env['res.partner'].sudo().search(
                    [('id', '=', res_partner.partner_id.id)])
                images_link = config_obj + \
                              ('/web/content/res.partner/%d/image_1920?updated_on=%s' %
                               (res_partner.partner_id.id, str(partner.write_date)))
            else:
                images_link = ""

            if res_partner.country_id:
                country_result = request.env['res.country'].search([('id', '=', int(res_partner.country_id.id))])
                if country_result:
                    country = {
                        'id': country_result.id,
                        'name': country_result.name
                    }
            if res_partner.state_id:
                state_result = request.env['res.country.state'].search([('id', '=', int(res_partner.state_id.id))])
                if state_result:
                    state = {
                        'id': state_result.id,
                        'name': state_result.name
                    }

            if res_partner.township_id:
                township_result = request.env['res.township'].search([('id', '=', int(res_partner.township_id.id))])
                if township_result:
                    township = {
                        'id': township_result.id,
                        'name': township_result.name
                    }

            response_val = {
                'name': res_partner.name,
                'street': res_partner.street if res_partner.street else "",
                'street2': res_partner.street2 if res_partner.street2 else "",
                'country': country,
                'state': state,
                'township': township,
                'city': res_partner.city if res_partner.city else "",
                'zip': res_partner.zip if res_partner.zip else "",
                'dob': res_partner.dob if res_partner.dob else "",
                'phone': res_partner.phone if res_partner.phone else "",
                'mobile': res_partner.mobile if res_partner.mobile else "",
                'email': res_partner.email if res_partner.email else "",
                'gender': res_partner.partner_id.gender if res_partner.partner_id.gender else "",
                'image': images_link,
                "default_warehouse": {
                    'id': res_partner.property_warehouse_id.id,
                    'name': res_partner.property_warehouse_id.name,
                    'code': res_partner.property_warehouse_id.code
                } if res_partner.property_warehouse_id else None,
                "user_group":
                    {
                        "id": res_partner.user_group_id.id,
                        "name": res_partner.user_group_id.name,
                        'is_main_group': res_partner.user_group_id.is_main_group,
                    },
                "user_role":
                    {
                        "id": res_partner.user_role_id.id,
                        "name": res_partner.user_role_id.name,
                        'code': res_partner.user_role_id.code,
                    },
                "has_approval_access": res_partner.user_role_id.has_approval_access,
                "has_saleorder_write_access": res_partner.user_role_id.has_saleorder_write_access,
                "menu_access": {
                    "show_box_receiving": res_partner.user_role_id.show_box_receiving,
                    "show_transfer": res_partner.user_role_id.show_transfer,
                    "show_kitting": res_partner.user_role_id.show_kitting,
                    "show_unbuild": res_partner.user_role_id.show_unbuild,
                    "show_stock_check": res_partner.user_role_id.show_stock_check,
                    "show_damage_products": res_partner.user_role_id.show_damage_products,
                    "show_stock_adjustment": res_partner.user_role_id.show_stock_adjustment,
                    "show_live_sale_session": res_partner.user_role_id.show_live_sale_session,
                    "show_request_product": res_partner.user_role_id.show_request_product,
                    "show_product_request_list": res_partner.user_role_id.show_product_request_list,
                    "show_product_receiving": res_partner.user_role_id.show_product_receiving,
                    "show_return_product": res_partner.user_role_id.show_return_product,
                    "show_return_product_list": res_partner.user_role_id.show_return_product_list,
                    "show_my_warehouse_stock": res_partner.user_role_id.show_my_warehouse_stock,
                    "show_customers": res_partner.user_role_id.show_customers,
                    "show_deliverable_customer": res_partner.user_role_id.show_deliverable_customer,
                    "show_packaging": res_partner.user_role_id.show_packaging,
                    "show_loading": res_partner.user_role_id.show_loading,
                    "show_delivering": res_partner.user_role_id.show_delivering,
                    "show_sale_order_list": res_partner.user_role_id.show_sale_order_list,
                },
                "function_access": {}
            }

        return valid_response(response_val)

    @validate_token
    @http.route("/api/user", methods=["PUT"], type='json', auth="none", csrf=False, custom_response=True)
    def post_profile(self):

        user_id = request.env.user.id
        res_partner = request.env['res.users'].sudo().search([('id', '=', int(user_id))]).partner_id

        data = json.loads(request.httprequest.data)
        try:
            if data.get("country_id"):
                chk_country_id = request.env['res.country'].sudo().search(
                    [('id', '=', int(data.get("country_id")))])
                if not chk_country_id:
                    return {"status": "fail", "error": "country id is invalid."}
            if data.get("state_id"):
                chk_country_state = request.env['res.country.state'].sudo().search(
                    [('id', '=', int(data.get("state_id")))])
                if not chk_country_state:
                    return {"status": "fail", "error": "state/division id is invalid."}
            if data.get("township_id"):
                chk_township = request.env['res.township'].sudo().search(
                    [('id', '=', int(data.get("township_id")))])
                if not chk_township:
                    return {"status": "fail", "error": "township id is invalid"}
            res_partner.sudo().write(data)
            response_val = {"status": "success"}
        except Exception as e:
            response_val = {"status": "fail"}

        return response_val

    @validate_token
    @http.route("/api/user/image", methods=["PUT"], type='http', auth="none", csrf=False)
    def post_profile_image(self):

        user_id = request.env.user.id
        profile_img_content_string = ""
        if 'profile_image' in request.httprequest.files:
            file = request.httprequest.files['profile_image']
            profile_img_content = request.httprequest.files['profile_image'].read()
            img_type = str(file.content_type)
            size = len(profile_img_content)
            if img_type == 'image/jpeg' or img_type == 'image/jpg' or img_type == 'image/png':
                if (int(size) / 1000000) <= 2:
                    profile_img_content_string = base64.b64encode(profile_img_content)
                    res_user = request.env['res.users'].sudo().search([('id', '=', int(user_id))])
                    try:
                        res_user.sudo().write({'image_1920': profile_img_content_string})
                        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
                        res_partner = res_user.partner_id
                        attachment = request.env['ir.attachment'].sudo().search(
                            [('res_id', '=', res_partner.id), ('res_field', '=', 'image_1920'),
                             ('res_model', '=', 'res.partner')])
                        image_link = ""
                        if attachment:
                            image_link = base_url + ('/web/content/res.partner/%d/image_1920?updated_on=%s' % (
                                res_partner.id, res_partner.write_date))
                        response_val = {"status": "success",
                                        "profile_image_url": image_link}
                    except Exception as e:
                        response_val = {"status": "message", "error": str(e)}
                else:
                    response_val = {"status": "fail", "message": "file size is too large. file size limit is 2 MB!"}
                    return valid_response(response_val)
            else:
                response_val = {"status": "fail", "message": "image type must be jpg,jpeg or png!"}
                return valid_response(response_val)

        else:
            response_val = {"status": "fail", "message": "image_1920 is not found!"}
        return valid_response(response_val)

    @validate_token
    @http.route("/api/user", methods=["DELETE"], type='http', auth="none", csrf=False)
    def delete_user_profile(self):
        response_val = {}
        headers = request.httprequest.headers
        password = headers.get("password")
        UserModel = request.env["res.users"].sudo()
        try:
            c_user = UserModel.search([("id", "=", int(request.uid))])  # c_user === CURRENT USER
            if password:
                db = request.session.db
                # check old password
                request.env['res.users']._check_credentials(password, request.env)
                # # uid = exp_login(db, c_user.login, password)
                # uid = True
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
                    token.sudo().browse(token.id).unlink()

                c_user.sudo().write(
                    {
                        # 'member_no': False,
                        'name': c_user.name + '(****no use****)',
                        'login': c_user.id,
                        'password': uuid.uuid4().hex,
                        # 'active': False
                        # 'partner_id': 0
                    })
                c_partner = c_user.partner_id
                c_partner.sudo().write({
                    'mobile': c_user.id,
                    # 'mobile': False,
                    'phone': c_user.id,
                })
                response_val = {"status": "success"}
            else:
                response_val = {"status": "fail", "message": "password is required."}
        except AccessDenied as ade:
            response_val = {"status": "fail", "message": "Incorrect Password"}
        return valid_response(response_val)
