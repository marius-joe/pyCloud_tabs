#!/usr/bin/env python3.7

# ******************************************
#  Dev:  marius-joe
# ******************************************
#  Export Safari tabs from iCloud to file
#  v1.4.2
# ******************************************

"""
Access the Safari tabs for all connected iCloud devices
System: macOS 10.12 Sierra and newer
"""

# txt Datei ohne Bindestriche bei device + Tabs bei urls testen

import os, sys, subprocess
import getpass
import sqlite3
from datetime import datetime
import json, zlib
import operator
import pyperclip #req for clipboard functionality

# toDo: check and fix relative imports
from .utils import utils_io

C_Path_CloudTabs_DB = '~/Library/Safari/CloudTabs.db'

# output
C_Path_Output_Folder = sys.argv[1]
C_File_Tabs = 'iCloud_Tabs.json'
C_File_Tab_Urls = 'iCloud_Tab_Urls.txt'


class PyCloud_Tabs():
    """
    Access the Safari tabs for all connected iCloud devices
    through the local database '~/Library/Safari/CloudTabs.db'

    2 tables from 'CloudTabs.db' are needed:
    'cloud_tab_devices' contains 'device_uuid', 'device_name'
    'cloud_tabs contains' 'device_uuid', 'title', 'url', 'position'

    We need: 'device_name', 'title', 'url', 'position'
    SQL Inner Join would be possible, but needs quadratic effort O(n^2) -
    joining the tables by a Python dictionary lookup is much more efficient
    """
    def __init__(self):
        self.path_cloudTabs_db = os.path.expanduser(C_Path_CloudTabs_DB)

    def get_tabs(self):
        db_conn = sqlite3.connect(self.path_cloudTabs_db)
        db_cursor = db_conn.cursor()

        db_cursor.execute("select device_uuid, device_name from cloud_tab_devices")
        iCloud_safari_devices_list = db_cursor.fetchall()

        db_cursor.execute("select device_uuid, title, url, position from cloud_tabs")
        iCloud_tabs_list = db_cursor.fetchall()
        db_conn.close()

        # create a dictionary with 'device_uuid': 'device_name' for fast name lookup
        iCloud_safari_devices_dict = {}
        for device in iCloud_safari_devices_list:
            device_uuid = device[0]
            device_name = device[1]
            iCloud_safari_devices_dict[device_uuid] = device_name

        iCloud_device_tabs = {}
        previous_device_uuid = ''
        previous_device_name = ''
        for tab in iCloud_tabs_list:
            device_uuid = tab[0]
            tab_title = tab[1]
            tab_url = tab[2]

            # tab order info is stored as a compressed byte-object in the cloud_tabs table
            position = json.loads(zlib.decompress(tab[3]), encoding='utf-8')
            tab_sortValue = position['sortValues'][0]['sortValue']

            tab_info_dict = {'title': tab_title, 'url': tab_url, 'sortValue': tab_sortValue}

            # in case the tabs are ordered by devices, you can reuse the previously looked up device_name
            if device_uuid != previous_device_uuid:
                device_name = iCloud_safari_devices_dict[device_uuid]
                previous_device_uuid = device_uuid
                previous_device_name = device_name
            else:
                device_name = previous_device_name

            if device_name in iCloud_device_tabs:
                iCloud_device_tabs[device_name].append(tab_info_dict)
            else:
                iCloud_device_tabs[device_name] = [tab_info_dict]

        # sort list of tab objects by 'sortValue'
        for device,tab_list in iCloud_device_tabs.items():
            tab_list.sort(key=operator.itemgetter('sortValue'))

        return iCloud_device_tabs
        # 'iCloud_device_tabs' structure:
        # {
        #     device1_name: [
        #         {'title': device1_tab1_title, 'url': device1_tab1_url, 'sortValue': device1_tab1_sortValue},
        #         {'title': device1_tab2_title, 'url': device1_tab2_url, 'sortValue': device1_tab2_sortValue}
        #     ],
        #     device2_name: [
        #         {'title': device2_tab1_title, 'url': device2_tab1_url, 'sortValue': device2_tab1_sortValue},
        #         {'title': device2_tab2_title, 'url': device2_tab2_url, 'sortValue': device2_tab2_sortValue}
        #     ]
        # }


    def get_tab_urls(self):
        iCloud_device_tab_urls = {}
        for device,tab_list in self.get_tabs().items():
            iCloud_device_tab_urls[device] = []
            for tab in tab_list:
                iCloud_device_tab_urls[device].append(tab['url'])
        return iCloud_device_tab_urls
        # 'iCloud_device_tab_urls' structure:
        # {
        #     device1_name: [
        #         device1_tab1_url,
        #         device1_tab2_url
        #     ],
        #     device2_name: [
        #         device2_tab1_url,
        #         device2_tab2_url
        #     ]
        # }


    def export_tabs(self, path_outputFolder):
        # Write iCloud_device_tabs dictionary to JSON file
        path_output = os.path.join(path_outputFolder, C_File_Tabs)
        utils_io.write_file(path_output, self.get_tabs(), mode='json', indent=2)

    def export_tab_urls(self, path_outputFolder, copy_to_clipboard=False):
        # Create url-list text file from iCloud_device_tab_urls dictionary
        output = ''
        for device,url_list in self.get_tab_urls().items():
            output += '----- ' + device + ' -----' + '\n'
            output += '\n'.join(url_list) + '\n\n'
        path_output = os.path.join(path_outputFolder, C_File_Tab_Urls)
        utils_io.write_file(path_output, output, mode='json', indent=2)

        if copy_to_clipboard:
            if pyperclip.is_available():
                pyperclip.copy(output)
            else:
                print("Clipboard Copy functionality unavailable!")


    # def export_markdownFile():
        # Create a Markdown file listing all the tabs from all devices
        # note: use . as time delimiter instead of : which is incompatible with Win file names
        # timestamp = datetime.now().strftime('%Y-%m-%d %H.%M.%S')
        # path_output = f"~/Desktop/alltabs_{timestamp}.md"

        # timestamp_printed = timestamp.replace('.', ':')
        # outtext = f'''
        # iCloud Tab Listing - {timestamp_printed}
        # Links from all devices:
        # '''

        # for device in iCloud_device_tabs:
            # outtext += '### %s\n\n' % device[0]
            # for tab in device[1]:
                # outtext += '* [%s](%s)\n' % (tab['Title'].replace("[", "/[").replace("]", "/]"), tab['URL'])
            # outtext += '\n'

        # utils_io.write_file(path_output, outtext, mode='json', indent=2)


    def open_tabs(self, exclude_thisDevice=True):
        # Get local machine's host and computer names to exclude both from the list
        hostname_proc = subprocess.Popen(
            ['scutil --get LocalHostName'], stdout=subprocess.PIPE, shell=True)
        (hostname_out, hostname_err) = hostname_proc.communicate()
        hostname = hostname_out.strip()

        computername_proc = subprocess.Popen(
            ['scutil --get ComputerName'], stdout=subprocess.PIPE, shell=True)
        (computername_out, computername_err) = computername_proc.communicate()
        computername = computername_out.strip()

        # Run the os 'open' command for each link found
        for device,url_list in self.get_tab_urls().items():
            if not (exclude_thisDevice and device in [hostname, computername.decode("utf-8")]):
                for url in url_list: os.system(f'open {url}')


if __name__ == "__main__":
    pyCloud_tabs = PyCloud_Tabs()
    pyCloud_tabs.export_tabs(C_Path_Output_Folder)
    pyCloud_tabs.export_tab_urls(C_Path_Output_Folder)
    print(
        '\n' + "iCloud tabs exported to:  " + C_Path_Output_Folder + os.path.sep + '\n' +
        'and copied to the clipboard' + '\n'
    )