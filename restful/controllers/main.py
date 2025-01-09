import ast
import functools
import json
import logging
import re
import base64
from odoo import http
from odoo.addons.restful.common import extract_arguments, invalid_response, valid_response
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.addons.restful.common import (
    alternative_json_response,
)

_logger = logging.getLogger(__name__)
from odoo.http import request, Response
from odoo.exceptions import AccessError, UserError
from odoo.tools import file_open, file_path, replace_exceptions


def validate_token(func):
    """."""

    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        """."""
        access_token = request.httprequest.headers.get("access_token")

        data = {
            'status': 'fail',
            'error': 'access token is expired or invalid'
        }
        if not access_token:
            # if request._request_type == 'http':
            #     return valid_response(data)
            # elif request._request_type == 'json':
            #     return data
            if request.httprequest.headers.get('Content-Type') == 'application/json':
                return data
            else:
                return valid_response(data)

        access_token_data = (
            request.env["api.access_token"].sudo().search(
                [("token", "=", access_token)], order="id DESC", limit=1)
        )

        # check user active or not
        if access_token_data and (
                access_token_data.user_id.active == False or access_token_data.user_id.is_approved_user == 'draft'):
            data = {
                'status': 'fail',
                'error': 'access token is expired or invalid'
            }
            if request.httprequest.headers.get('Content-Type') == 'application/json':
                return data
            else:
                return valid_response(data)

        if access_token_data.find_one_or_create_token(user_id=access_token_data.user_id.id) != access_token:
            if request.httprequest.headers.get('Content-Type') == 'application/json':
                return data
            else:
                return valid_response(data)

        # request.session.uid = access_token_data.user_id.id
        # request.uid = access_token_data.user_id.id
        # request.user = access_token_data.user_id
        request.update_env(access_token_data.user_id, request.env.context)
        return func(self, *args, **kwargs)

    return wrap


def public_validate_token(func):
    """."""

    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        """."""
        access_token = request.httprequest.headers.get("access_token")

        if not access_token:
            request.is_guest = True
            request.user = None
        else:
            request.is_guest = False
            access_token_data = (
                request.env["api.access_token"].sudo().search(
                    [("token", "=", access_token)], order="id DESC", limit=1)
            )

            if not access_token_data and (
                    access_token_data.user_id.active == False or access_token_data.find_one_or_create_token(
                user_id=access_token_data.user_id.id) != access_token or access_token_data.user_id.is_approved_user == 'draft'):
                data = {
                    'status': 'fail',
                    # 'code': 'token',
                    'error': "access token is expired or invalid"
                }
                # if request._request_type == 'http':
                #     return valid_response(data)
                # elif request._request_type == 'json':
                #     return data
                if request.httprequest.headers.get('Content-Type') == 'application/json':
                    return data
                else:
                    return valid_response(data)

            request.session.uid = access_token_data.user_id.id
            request.uid = access_token_data.user_id.id
            request.user = access_token_data.user_id
        return func(self, *args, **kwargs)

    return wrap


_routes = ["/api/<model>", "/api/<model>/<id>", "/api/<model>/<id>/<action>"]


class APIController(http.Controller):
    """."""

    def __init__(self):
        self._model = "ir.model"

    @validate_token
    @http.route(_routes, type="http", auth="none", methods=["GET"], csrf=False)
    def get(self, model=None, id=None, **payload):
        try:
            ioc_name = model
            model = request.env[self._model].search(
                [("model", "=", model)], limit=1)
            if model:
                domain, fields, offset, limit, order = extract_arguments(
                    payload)
                data = request.env[model.model].search_read(
                    domain=domain, fields=fields, offset=offset, limit=limit, order=order,
                )
                if id:
                    domain = [("id", "=", int(id))]
                    data = request.env[model.model].search_read(
                        domain=domain, fields=fields, offset=offset, limit=limit, order=order,
                    )
                if data:
                    return valid_response(data)
                else:
                    return valid_response(data)
            return invalid_response(
                "invalid object model", "The model %s is not available in the registry." % ioc_name,
            )
        except AccessError as e:

            return invalid_response("Access error", "Error: %s" % e.name)

    @validate_token
    @http.route(_routes, type="http", auth="none", methods=["POST"], csrf=False)
    def post(self, model=None, id=None, **payload):
        """Create a new record.
        Basic sage:
        import requests

        headers = {
            'content-type': 'application/x-www-form-urlencoded',
            'charset': 'utf-8',
            'access-token': 'access_token'
        }
        data = {
            'name': 'Babatope Ajepe',
            'country_id': 105,
            'child_ids': [
                {
                    'name': 'Contact',
                    'type': 'contact'
                },
                {
                    'name': 'Invoice',
                   'type': 'invoice'
                }
            ],
            'category_id': [{'id': 9}, {'id': 10}]
        }
        req = requests.post('%s/api/res.partner/' %
                            base_url, headers=headers, data=data)

        """
        import ast

        payload = payload.get("payload", {})
        ioc_name = model
        model = request.env[self._model].search(
            [("model", "=", model)], limit=1)
        values = {}
        if model:
            try:
                # changing IDs from string to int.
                for k, v in payload.items():

                    if "__api__" in k:
                        values[k[7:]] = ast.literal_eval(v)
                    else:
                        values[k] = v

                resource = request.env[model.model].create(values)
            except Exception as e:
                request.env.cr.rollback()
                return invalid_response("params", e)
            else:
                data = resource.read()
                if resource:
                    return valid_response(data)
                else:
                    return valid_response(data)
        return invalid_response("invalid object model", "The model %s is not available in the registry." % ioc_name, )

    @validate_token
    @http.route(_routes, type="http", auth="none", methods=["PUT"], csrf=False)
    def put(self, model=None, id=None, **payload):
        """."""
        payload = payload.get('payload', {})
        try:
            _id = int(id)
        except Exception as e:
            return invalid_response("invalid object id", "invalid literal %s for id with base " % id)
        _model = request.env[self._model].sudo().search(
            [("model", "=", model)], limit=1)
        if not _model:
            return invalid_response(
                "invalid object model", "The model %s is not available in the registry." % model, 404,
            )
        try:
            request.env[_model.model].sudo().browse(_id).write(payload)
        except Exception as e:
            request.env.cr.rollback()
            return invalid_response("exception", e.name)
        else:
            return valid_response("update %s record with id %s successfully!" % (_model.model, _id))

    @validate_token
    @http.route(_routes, type="http", auth="none", methods=["DELETE"], csrf=False)
    def delete(self, model=None, id=None, **payload):
        """."""
        try:
            _id = int(id)
        except Exception as e:
            return invalid_response("invalid object id", "invalid literal %s for id with base " % id)
        try:
            record = request.env[model].sudo().search([("id", "=", _id)])
            if record:
                record.unlink()
            else:
                return invalid_response("missing_record", "record object with id %s could not be found" % _id, 404, )
        except Exception as e:
            request.env.cr.rollback()
            return invalid_response("exception", e.name, 503)
        else:
            return valid_response("record %s has been successfully deleted" % record.id)

    @validate_token
    @http.route(_routes, type="http", auth="none", methods=["PATCH"], csrf=False)
    def patch(self, model=None, id=None, action=None, **payload):
        """."""
        try:
            _id = int(id)
        except Exception as e:
            return invalid_response("invalid object id", "invalid literal %s for id with base " % id)
        try:
            record = request.env[model].sudo().search([("id", "=", _id)])
            _callable = action in [method for method in dir(
                record) if callable(getattr(record, method))]
            if record and _callable:
                # action is a dynamic variable.
                getattr(record, action)()
            else:
                return invalid_response(
                    "missing_record",
                    "record object with id %s could not be found or %s object has no method %s" % (
                        _id, model, action),
                    404,
                )
        except Exception as e:
            return invalid_response("exception", e, 503)
        else:
            return valid_response("record %s has been successfully patched" % record.id)


class WebBinaryController(http.Controller):

    @http.route(['/web/content',
                 '/web/content/<string:xmlid>',
                 '/web/content/<string:xmlid>/<string:filename>',
                 '/web/content/<int:id>',
                 '/web/content/<int:id>/<string:filename>',
                 '/web/content/<string:model>/<int:id>/<string:field>',
                 '/web/content/<string:model>/<int:id>/<string:field>/<string:filename>'], type='http', auth="public")
    # pylint: disable=redefined-builtin,invalid-name
    def public_content_common(self, xmlid=None, model='ir.attachment', id=None, field='raw',
                       filename=None, filename_field='name', mimetype=None, unique=False,
                       download=False, access_token=None, nocache=False):

        with replace_exceptions(UserError, by=request.not_found()):
            record = request.env['ir.binary'].sudo()._find_record(xmlid, model, id and int(id), access_token)
            stream = request.env['ir.binary'].sudo()._get_stream_from(record, field, filename, filename_field, mimetype)
        send_file_kwargs = {'as_attachment': download}
        if unique:
            send_file_kwargs['immutable'] = True
            send_file_kwargs['max_age'] = http.STATIC_CACHE_LONG
        if nocache:
            send_file_kwargs['max_age'] = None

        res = stream.get_response(**send_file_kwargs)
        res.headers['Content-Security-Policy'] = "default-src 'none'"
        return res
