#
#
#
#
#
#
#

import bpy, addon_utils
import urllib.request, mimetypes, http, xml, os, sys, re, tempfile
from urllib.error import URLError, HTTPError
from os import path
from bpy.props import *

def extract_host_from(url):
    if url.find("://") == -1 :
        host = ""
    else:
        split = url.split("://", 1)
        if len(split) == 2:
            split = split[1].split("/", 1)
        host = split[0]
    return host






def call_url(self, url, supported_extensions=None):
    response = None
    
    if url.startswith("blender://"):
        print("URL is a blender data source")

        ds = url[10:].split("/")
        mod  = sys.modules[ds[0]]
        func = ds[1]
        print("Call %s.%s" % (mod,func)) 
        data_source = getattr(mod,func)
        data = data_source()
        extension = None
        filename = None
    else:

        try:

            print("Calling:[%s]" % url)
            response = urllib.request.urlopen(url)
        except HTTPError as e:
            msg = 'Feed Reader: The server rejected to process the request.'
            print(msg)
            print('Error code: ', e.code)
            self.report({'ERROR'},("%s.\nThe reported Error Code was: %d:(%s)" %(msg, e.code, http.client.responses[e.code])))
            return None, None, None
        except URLError as e:
            msg = 'Feed Reader: The server did not respond.'
            print(msg)
            print('Reason: ', e.reason)
            self.report({'ERROR'},("%s.\n Reason:%s\nDownload aborted." %(msg, e.reason)))
            return None, None, None
        except:
            msg = "Feed Reader: Could not get data from server HTTP for unknown reason."
            print("system info:", sys.exc_info())
            print(msg)
            self.report({'ERROR'},("%s.\nDownload aborted." %(msg)))
            return None, None, None

        data = None

        if response is None:

            filename  = os.path.basename(url)
            extension = os.path.splitext(filename)[1]
        else:

            extension, filename = get_extension_and_name(self, response, supported_extensions)

    return response, extension, filename

def update_url(self, url, supported_extensions=None):
    data, ext, fname = call_url(self, url, supported_extensions)        
    return data

def create_feed_url(link, userid="", password=""):
    url = link.replace("$userid",userid.replace(" ","+"))
    url = url.replace("$password",password.replace(" ","+"))

    url = prepare_url(url)
    return url
    

    







def prepare_url(href, query=None):
    url = ""
    




    if sys.platform.lower().startswith("win"):
        if href[1] == ":": # is a windows file
            url = "file:///"
    else:
        if href.startswith("/"): # is a unix file
            url = "file://"
    url += href
    

    if not query is None and href.startswith("http"):
        hasQuery = (url.find("?") != -1)
        if not hasQuery:
            url += "?"
        else:
            if not url.endswith(("?", "&")):
                url +="&"
        url += query

    return url

    







def get_extension_and_name(self, response, supported_extensions=None):

    filename = None
    extension = None
    

    content_disposition = response.getheader('content-disposition')
    if not content_disposition is None:
        namep_match = self.filename_pattern.match(content_disposition)
        if not namep_match is None:
            filename = namep_match.group(1)
            extp_match = self.extension_pattern.match(filename)
            if not extp_match is None:
                extension = "." + extp_match.group(1)
        return extension, filename
    

    content_type = response.getheader('content-type')
    if not content_type is None:

        extension = mimetypes.guess_extension(content_type.lower())
          

        if supported_extensions == None or extension in supported_extensions:
            path = urllib.parse.urlparse(response.geturl()).path
            fn   = path.rpartition('/')[2]
            ext  = '.' + fn.rpartition('.')[2]
            if supported_extensions == None or ext in supported_extensions:
                filename = fn
            return extension, filename;

    return None, None
