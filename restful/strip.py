import pytz
import re

class RemoveHtmlTags():

    def remove_html_tags(self,text):
        """Remove html tags from a string"""
        result = ""
        if text:
            clean = re.compile('<.*?>')
            result = re.sub(clean, '', text)
        return result

    def remove_html_tags_withcount(self,text,tex_count):
        """Remove html tags from a string"""
        result = ""
        stop = 100
        if tex_count and int(tex_count) > 0:
            stop = tex_count
        if text:
            clean = re.compile('<.*?>')
            result = re.sub(clean, '', text)
            if result and len(result) > stop:
                result = result[0: stop:]
        return result

    def check_input_format(self,txt):
        x = re.search("^([a-zA-Z0-9]+)$|^(([^\|]+\|)+[^\|]+)$", txt)
        return x