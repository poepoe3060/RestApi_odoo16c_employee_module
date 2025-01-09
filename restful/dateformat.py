import pytz
from datetime import datetime

def change_local_timezone(date):
    get_date = str(date)
    index_1 = get_date.find('.')

    if index_1 != -1:
        remove_str = get_date[int(index_1):]
        result_date = get_date.replace(remove_str, "")
    else:
        result_date = get_date

    now_utc_date = datetime.strptime(result_date, "%Y-%m-%d %H:%M:%S")

    now_rangoon = now_utc_date.astimezone(pytz.timezone('Asia/Rangoon'))
    final_date = now_rangoon.strftime("%Y-%m-%d %H:%M:%S")

    return final_date

def change_local_time(date):
    get_date = str(date)
    index_1 = get_date.find('.')

    if index_1 != -1:
        remove_str = get_date[int(index_1):]
        result_date = get_date.replace(remove_str, "")
    else:
        result_date = get_date

    now_utc_date = datetime.strptime(result_date, "%Y-%m-%d %H:%M:%S")

    now_rangoon = now_utc_date.astimezone(pytz.timezone('Asia/Rangoon'))
    final_date = now_rangoon.strftime("%m/%d/%Y")
    return final_date