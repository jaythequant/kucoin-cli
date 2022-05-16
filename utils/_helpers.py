from datetime import datetime


def parse_date(date_string):
    if ":" in date_string:
        dt_obj = datetime.strptime(
            date_string, "%Y-%m-%d %H:%M:%S"
        )
    else:
        dt_obj = datetime.strptime(
            date_string, "%Y-%m-%d"
        )
    return dt_obj
