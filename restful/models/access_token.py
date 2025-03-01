import hashlib
import logging
import os
import pytz
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)
expires_in = "restful.access_token_expires_in"

def nonce(length=40, prefix="access_token"):
    rbytes = os.urandom(length)
    return "{}_{}".format(prefix, str(hashlib.sha1(rbytes).hexdigest()))


class APIAccessToken(models.Model):
    _name = "api.access_token"
    _description = "API Access Token"

    token = fields.Char("Access Token", required=True)
    user_id = fields.Many2one("res.users", string="User", required=True)
    expires = fields.Datetime(string="Expires", required=True)
    scope = fields.Char(string="Scope")

    def find_one_or_create_token(self, user_id=None, create=False):
        if not user_id:
            user_id = self.env.user.id

        expires = datetime.now((pytz.timezone('Asia/Rangoon'))) + timedelta(
            days=int(self.env.ref(expires_in).sudo().value))
        expires_date = expires.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        access_token = self.env["api.access_token"].sudo().search([("user_id", "=", user_id)], order="id DESC", limit=1)
        if access_token:
            # azp update
            update_data = access_token.write(
                {
                    "expires": expires_date
                }
            )
            if update_data:
                access_token = access_token[0]
        if not access_token and create:
            vals = {
                "user_id": user_id,
                "scope": "userinfo",
                "expires": expires_date,
                "token": nonce(50),
            }
            access_token = self.env["api.access_token"].sudo().create(vals)
        if not access_token:
            return None
        return access_token.token

    def _allow_scopes(self, scopes):
        self.ensure_one()
        if not scopes:
            return True

        provided_scopes = set(self.scope.split())
        resource_scopes = set(scopes)

        return resource_scopes.issubset(provided_scopes)


class Users(models.Model):
    _inherit = "res.users"
    token_ids = fields.One2many("api.access_token", "user_id", string="Access Tokens")
