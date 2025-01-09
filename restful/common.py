import logging
import datetime
import time
import json
import ast
import requests
import werkzeug.wrappers
import re
import pytz
from odoo import models, fields, api, tools, _
from odoo.addons.web.controllers.main import ensure_db
from odoo.http import request, Response
from odoo.tools import date_utils
from odoo.exceptions import ValidationError, UserError
from odoo.addons.restful.onesignal import OneSignal
import threading

_logger = logging.getLogger(__name__)

STATUS_CODES = {
    200: {"code": 200, "code_message": "success", "description": "Indicates that request has succeeded."},
    201: {"code": 201, "code_message": "created",
          "description": "Indicates that request has succeeded and a new resource has been created as a result."},
    202: {"code": 202, "code_message": "accepted",
          "description": "Indicates that the request has been received but not completed yet. It is typically used in log running requests and batch processing."},
    400: {"code": 400, "code_message": "bad_request",
          "description": "The request could not be understood by the server due to incorrect syntax. The client SHOULD NOT repeat the request without modifications."},
    401: {"code": 401, "code_message": "unauthorized",
          "description": "Indicates that the request requires user authentication information. The client MAY repeat the request with a suitable Authorization header field."},
    404: {"code": 404, "code_message": "not_found", "description": "The server can not find the requested resource."}
}


def alternative_json_response(self, result=None, error=None):
    if error is not None:
        response = error

    if result is not None:
        response = result

    mime = 'application/json'

    body = json.dumps(response, default=date_utils.json_default)

    return Response(

        body, status=error and error.pop('http_status', 200) or 200,

        headers=[('Content-Type', mime), ('Content-Length', len(body))]

    )


def send_sms(self, phone, sms):
    ICPSudo = request.env['ir.config_parameter'].sudo()
    seller_name = ICPSudo.get_param('inherit_models.seller_name')
    auth_token = ICPSudo.get_param('inherit_models.sms_api_key')
    hed = {"Authorization": "Bearer " + auth_token}
    data = {"to": "" + str(phone) + "",
            "message": sms,
            "sender": seller_name}
    url = "https://smspoh.com/api/v2/send"
    poh_response = requests.post(url, json=data, headers=hed)
    return poh_response.status_code


lock = threading.Lock()


class InheritProductTemplate(models.AbstractModel):
    _name = 'sent.notification'

    def sent_all_notifications(self, noti_code, user, placeholders):
        result = None
        with lock:
            try:
                for i in range(2):
                    print("???????????working ???????")
                with api.Environment.manage():

                    new_cr = self.pool.cursor()
                    self = self.with_env(self.env(cr=new_cr))
                    user = self.env['res.users'].sudo().browse(int(user.id))

                    if not user:
                        raise UserError(_('User Not Found !'))

                    # ICPSudo = self.env['ir.config_parameter'].sudo()
                    send_notification = self.env['notification.setting'].search([('code', '=', noti_code)], limit=1)
                    if not send_notification:
                        raise UserError(_('Notification setting fot this message is not found !'))
                    title = send_notification.name
                    message = send_notification.message
                    if send_notification.noti_type == 'sms':
                        message = send_notification.email_template

                    if placeholders:
                        ####replace placeholders with values####
                        placeholders_value_list = placeholders
                        placeholders = re.findall(r'\{([^}]+)\}', message)
                        placeholders_key_list = ['{' + placeholder + '}' for placeholder in placeholders]
                        ########################################

                        placeholder_dict = {}
                        for placeholder_value in placeholders_value_list:
                            for key, value in placeholder_value.items():
                                placeholder_key = '{' + key + '}'
                                if placeholder_key in placeholders_key_list:
                                    placeholder_dict[placeholder_key] = value
                        print(placeholder_dict)

                        if send_notification.developer_test:
                            placeholder_dict_str = json.dumps(placeholder_dict)
                            message = placeholder_dict_str
                        else:
                            for placeholder, value in placeholder_dict.items():
                                message = message.replace(placeholder, str(value))
                        print(message)

                    ###SEND SMS####
                    if send_notification.noti_type == 'sms':
                        phone = user.partner_id.phone or user.partner_id.mobile
                        if not phone:
                            raise UserError(_('Phone Number Not Found!'))
                        result = self.send_sms_new(phone, message)

                    #####SEND PUSH NOTI ###
                    elif send_notification.noti_type == 'push_noti':
                        OneSignal = self.env['onesignal'].sudo()
                        if send_notification.create_noti:
                            result = "errors"
                            noti = self.env['noti'].sudo()
                            if user.mobile_token:
                                group_values = {
                                    'name': title,
                                    'message': message,
                                    'user_id': int(user.id)
                                }
                                noti.create(group_values)
                                result = OneSignal.sendUser(message, title, user.mobile_token)

                            # return result
                        else:
                            if user.mobile_token:
                                result = OneSignal.sendUser(message, title, user.mobile_token)
                            # return result
                    else:
                        result = self.send_email(user, send_notification, message)

                    print(">>>>>>", result, type(result))
                    if result == 'success' or result == 200:
                        log_vals = {
                            "message": send_notification.message,
                            "email_template": send_notification.email_template if send_notification.noti_type == 'email' else None,
                            "recipient_ids": user,
                            "noti_type": send_notification.noti_type,
                            "created_date_time": datetime.datetime.now()
                        }
                        self.env['notification.log'].sudo().create(log_vals)

                    new_cr.commit()
                    new_cr.close()

            except Exception as e:
                print("Exception:", e)

        return result

    def send_sms_new(self, phone, sms):
        data = {}
        ICPSudo = self.env['ir.config_parameter'].sudo()
        provider_id = ICPSudo.get_param('sms_provider.sms_provider_id')

        if not provider_id:
            return "errors"

        sms_provider = self.env['sms.provider'].sudo().search([('id', '=', int(provider_id))], limit=1)
        seller_name = sms_provider.sender_id
        auth_token = sms_provider.api_key
        hed = {"Authorization": "Bearer " + auth_token}
        url = sms_provider.endpoint_url

        if sms_provider.name == 'sms poh':
            data = {"to": "" + str(phone) + "",
                    "message": sms,
                    "sender": seller_name}

        elif sms_provider.name == 'boom sms':
            first_two_letters = phone[:2]
            if first_two_letters == "95":
                phone = phone
            elif first_two_letters == "09":
                reduce_first_two_letter = phone[2:]
                phone = "959" + reduce_first_two_letter
            data = {"to": "" + str(phone) + "",
                    "text": sms,
                    "from": seller_name}
        provider_response = requests.post(url, json=data, headers=hed)
        return provider_response.status_code

    def send_email(self, user, notification, message):
        # send email
        result = {}
        # order = request.env['custom.purchase'].sudo().search([('id', '=', int(order_id))], limit=1)
        # config_obj = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        # logo = config_obj + ('/inherit_models/static/src/pladico.png')

        # ICPSudo = request.env['ir.config_parameter'].sudo()
        receiver_email = user.login
        if receiver_email:
            # result['img_url'] = logo
            result['receiver_email'] = receiver_email
            result['subject'] = notification.name
            result['message'] = message

            # template_id_user = self.env.ref('restful.notification_email_template',raise_if_not_found=False).id
            # template_user = self.env['mail.template'].browse(template_id_user)
            template_user = self.env.ref('restful.notification_email_template', raise_if_not_found=False)
            result = template_user.with_context(result).sudo().send_mail(notification.id, force_send=True)

            return 'success'


def default(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if isinstance(o, bytes):
        return str(o)


def valid_response(data, status=200):
    """Valid Response
    This will be return when the http request was successfully processed."""
    # data = {"count": len(data), "data": data}
    return werkzeug.wrappers.Response(
        status=status, content_type="application/json; charset=utf-8", response=json.dumps(data, default=default),
    )


def invalid_response(typ, message=None, status=401):
    """Invalid Response
    This will be the return value whenever the server runs into an error
    either from the client or the server."""
    # return json.dumps({})
    return werkzeug.wrappers.Response(
        status=status,
        content_type="application/json; charset=utf-8",
        response=json.dumps(
            {"type": typ, "message": str(message) if str(message) else "wrong arguments (missing validation)", },
            default=datetime.datetime.isoformat,
        ),
    )


def extract_arguments(limit="80", offset=0, order="id", domain="", fields=[]):
    """Parse additional data  sent along request."""
    limit = int(limit)
    expresions = []
    if domain:
        expresions = [tuple(preg.replace(":", ",").split(",")) for preg in domain.split(",")]
        expresions = json.dumps(expresions)
        expresions = json.loads(expresions, parse_int=True)
    if fields:
        fields = fields.split(",")

    if offset:
        offset = int(offset)
    return [expresions, fields, offset, limit, order]


class Map(dict):
    """
    Example:
    m = Map({'first_name': 'Eduardo'}, last_name='Pool', age=24, sports=['Soccer'])
    """

    def __init__(self, *args, **kwargs):
        super(Map, self).__init__(*args, **kwargs)
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self[k] = v

        if kwargs:
            for k, v in kwargs.items():
                self[k] = v

    def __getattr__(self, attr):
        return self.get(attr)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        super(Map, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(Map, self).__delitem__(key)
        del self.__dict__[key]
