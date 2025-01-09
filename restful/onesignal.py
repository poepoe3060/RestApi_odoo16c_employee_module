import requests
import json
from odoo.http import request, Response
from odoo import models, fields,api

class OneSignal(models.AbstractModel):
    _name = 'onesignal'
    _description = 'Onesignal'

    # url = provider_id.endpoint_url
    # app_id =provider_id.app_id
    # channel_id ="31747633-ed7a-47e3-8f66-440147d0df25"
    # headers = {
    #     "Accept": "application/json",
    #     "Authorization": f"Basic {provider_id.api_key}",
    #     "Content-Type": "application/json"
    # }
    def sendAll(self, content, name, image=None):
        endpoint_url, app_id, headers = self.call_provider()
        payload = {
            "app_id": app_id,
            # "android_channel_id": self.channel_id,
            "included_segments": ['Subscribed Users'],
            "headings": {
                "en": name,
            },
            "contents": {
                "en": content,
            },
            'large_icon': image,
            # 'big_picture':"https://static.fotor.com/app/features/img/ft_bg_banner.jpg",
            "name": name
        }

        response = requests.post(endpoint_url, json=payload, headers=headers)
        data = json.loads(response.text)
        result = "success"
        if data:
            if "errors" in data:
                result = "errors"

        return result

    def sendUser(self, content, name, target, image=None):
        endpoint_url, app_id, headers = self.call_provider()
        payload = {
            "app_id": app_id,
            # "android_channel_id": self.channel_id,
            "include_player_ids": [target],
            "headings": {
                "en": name,
            },
            "contents": {
                "en": content,
            },
            'large_icon': image,
            # 'big_picture':"https://static.fotor.com/app/features/img/ft_bg_banner.jpg",
            "name": name
        }

        response = requests.post(endpoint_url, json=payload, headers=headers)
        data = json.loads(response.text)

        result = "success"
        if "errors" in data:
            result = "errors"

        return result

    def call_provider(self):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        provider_id = ICPSudo.get_param('push_noti_provider.push_noti_provider_id')
        provider_id = self.env['push.noti.provider'].sudo().search([('id', '=', int(provider_id))], limit=1)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Basic {provider_id.api_key}",
            "Content-Type": "application/json"
        }
        return provider_id.endpoint_url, provider_id.app_id, headers
