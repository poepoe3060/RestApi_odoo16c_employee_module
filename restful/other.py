import pytz
import re
from odoo.http import request
from datetime import date, datetime
import numpy as np
import random


def get_user_type_with_pricelist(partner_id):
    result = {}
    if partner_id:
        partner = request.env['res.partner'].sudo().search([('id', '=', int(partner_id))], limit=1)
        if partner:
            result = {
                "partner_id": partner_id,
                "user_type_id": partner.user_type_id.id,
                "user_type_name": partner.user_type_id.name,
                "price_list_id": partner.user_type_id.pricelists_id.id
            }
    return result


def get_pricelist_price(product_tmpl_id, price_list_id, return_list=True):
    product_ptl = request.env['product.template'].sudo().search([('id', '=', int(product_tmpl_id))], limit=1)
    price = []
    default_uom = product_ptl.uom_id.id
    uom_category = product_ptl.uom_id.category_id
    uom_domain = [('category_id', '=', uom_category.id)]
    data = {
        'quantity': 1,
        'price': product_ptl.list_price,
        'uom': product_ptl.uom_id.name
    }

    if price_list_id:
        price_list = request.env['product.pricelist'].sudo().search([("id", "=", int(price_list_id))], limit=1)
        domain = [('applied_on', '=', '1_product'), ('product_tmpl_id', '=', int(product_tmpl_id)),
                  ('pricelist_id', '=', int(price_list_id)),
                  '|', '&',
                  ('date_start', "=", False), ('date_end', "=", False),
                  '&', ('date_start', "<=", datetime.now()), ('date_end', ">=", datetime.now())]

        if not return_list:
            domain.append(('min_quantity', "=", 1))
            domain.append(('uom_id', "=", product_ptl.uom_id.id))
            uom_domain.append(('id', "=", product_ptl.uom_id.id))

        fields = ['fixed_price', 'min_quantity', 'uom_id']
        item = price_list.item_ids.search_read(domain, fields=fields, order='min_quantity')

        if item:
            # executed = False  # Flag variable
            for i in item:
                # if not executed and not (i['min_quantity'] == 1 and i['uom_id'][0] == product_ptl.uom_id.id):
                #     price.append(data)
                #     executed = True  # Set the flag to True after executing the code once

                if i['min_quantity']:
                    price.append({
                        'quantity': int(i['min_quantity']),
                        'price': round(i['fixed_price'], 2),
                        'uom': i['uom_id'][1]
                    })

            if not search(item, 1, product_ptl.uom_id.id):
                price.append(data)
            uom_list = list(set([i['uom_id'][0] for i in item]))
            if len(uom_list) == 1:
                uom_domain.append(('id', '!=', uom_list[0]))
            else:
                uom_domain.append(('id', 'not in', uom_list))

        other_uoms = request.env['uom.uom'].sudo().search(uom_domain)
        for uom in other_uoms:
            base_price = get_total_qty(uom_obj=uom, qty=product_ptl.list_price)
            converted_price = uom_converter(None, product_ptl, base_price, uom)
            data = {
                'quantity': 1,
                'price': converted_price,
                'uom': uom.name
            }
            price.append(data)

    return sorted(price, key=lambda x: x['uom'], reverse=False)


def search(list, platform, default_uom):
    for i in list:
        if i['min_quantity'] == platform and i['uom_id'][0] == default_uom:
            return True
    return False


def get_total_qty(uom_obj, qty):
    total_qty = 0
    if uom_obj.uom_type == 'bigger':
        total_qty += (qty * uom_obj.factor_inv)
    elif uom_obj.uom_type == 'smaller':
        total_qty += (qty / uom_obj.factor)
    else:
        total_qty += qty
    return total_qty


def uom_converter(line_id, product_obj, total_qty, uom_id):
    uom_obj = None
    if product_obj:
        uom_obj = product_obj.uom_id
    if line_id:
        uom_obj = line_id.product_uom
    converted_qty = 0
    if uom_obj:
        if uom_id != uom_obj.id:
            if uom_obj.uom_type == 'bigger':
                converted_qty = (total_qty / uom_obj.factor_inv)
            elif uom_obj.uom_type == 'smaller':
                converted_qty = (total_qty * uom_obj.factor)
            else:
                converted_qty = total_qty
        else:
            converted_qty = total_qty

    return converted_qty


def sale_order_authorization(user_id, order_id):
    result = True
    if not user_id:
        partner_id = 4
    else:
        partner_id = user_id.partner_id.id
    domain = [('id', '=', int(order_id)), ('partner_id', '=', int(partner_id))]
    sale_order = request.env['sale.order'].sudo().search(domain)
    if not sale_order:
        result = False
    return result
