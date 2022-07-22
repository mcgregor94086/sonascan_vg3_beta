import logging
import os
# import subprocess
from datetime import datetime
from pathlib import Path

import PySimpleGUI as sg

from attach_gcp import attach_gcp
from attach_images import attach_images
from config_wifi import config_wifi
from convert_obj_to_stl import convert_obj_to_stl
from crop_obj import crop_obj
from demo import demo
from download_obj import download_obj
from get_linux_cameras import get_linux_cameras_list
from get_mac_cameras import get_mac_cameras_list
from get_photoscene_id import get_photoscene_id
from get_scanner_id import get_scanner_id
from get_scan_id import get_scan_id

from GUI_defs import window, images_dir, scans_dir, settings_layout, disabled_scan_button
from launch_modeling import launch_modeling
from poll_for_completion import poll_for_completion
from scan import scan
from send_emails import send_emails
from show_images import show_images
from show_model import show_model
from sonascan_file_paths import sonautics_logs_dir_path, sonautics_root_dir_path, sonautics_scans_dir_path
from terminate import terminate
# from upload_images import upload_images
from upload_obj_and_stl import upload_obj_and_stl
# from config_settings import config_settings

# enable for run time debugging
# import pdb
# pdb.set_trace()


def main():
    scan_disabled_state = True
    # ############################## SET UP LOGGING #########################
    # TURN ON LOGGING TO SONASCAN.LOG
    log_file_path = os.path.join(sonautics_logs_dir_path, "sonascan.log")
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG,
                        format="%(asctime)s:%(levelname)s:%(filename)s:%(lineno)d:%(funcName)s:%(message)s"
                        )
    # logging.debug(sg.main_get_debug_data())
    # ############################## SET UP LOGGING #########################

    # ############################## GET SCANNER_ID AND DIR #########################
    scanner_id_file_path = os.path.join(sonautics_root_dir_path, 'scanner_id.txt')
    scanner_id, scanner_dir = get_scanner_id(sonautics_scans_dir_path, scanner_id_file_path)

    try:
        os.makedirs(scanner_dir, mode=770, exist_ok=True)
    except OSError as error:
        print("Directory '%s' can not be created", error)
    logging.info(f'scanner_id = {scanner_id}, scanner_dir = {scanner_dir}')
    # ############################## END GET SCANNER_ID #########################

    # ############################## GET CAMERAS LIST #########################
    cameras_list = list()
    usb_map_dict = dict()
    window['_SCAN_BUTTON_'].update(image_filename=disabled_scan_button)
    window['_ACTION_STATUS_LINE_1_'].update("Discovering Cameras.")
    window['_ACTION_STATUS_LINE_2_'].update("Please wait while we test all cameras.")
    window['_PROGRESS_BAR_'].update(0)
    window['_ACTION_STATUS_LINE_3_'].update("")
    window['_SCAN_ID_'].update('')
    window.refresh()

    if sg.running_linux():
        print('CALLING get_linux_cameras_list()')
        # cameras_list, usb_map_dict = get_linux_cameras_list()
        window.perform_long_operation(lambda: get_linux_cameras_list(window), '-CAMERAS_LOADED-')
        print('RETURNING FROM get_linux_cameras_list()')

    elif sg.running_mac():
        print('CALLING get_mac_cameras_list()')
        # cameras_list, usb_map_dict = get_mac_cameras_list()
        window.perform_long_operation(get_mac_cameras_list(window), '-CAMERAS_LOADED-')
        print('RETURNING FROM get_mac_cameras_list()')

    else:
        logging.error("this software only runs on Linux and macOS")
        terminate(-1, "this software only runs on Linux and macOS")

        # ############################## END GET CAMERAS LIST #########################

    #  ************************************************************************************************************
    #   Define window events
    #  ************************************************************************************************************
    window['_SCAN_BUTTON_'].bind('<Button-1>', '+LEFT CLICK+')
    # window['_SCAN_BUTTON_'].bind('<Button-2>', '+MIDDLE CLICK+')
    # window['_SCAN_BUTTON_'].bind('<Button-3>', '+RIGHT CLICK+')
    window['_SCAN_BUTTON_'].bind('<Enter>', '+MOUSE OVER+')
    window['_SCAN_BUTTON_'].bind('<Leave>', '+MOUSE AWAY+')
    mouse_away_state_image = os.path.join(images_dir, 'scan-button-small-reg.png')
    # mouse_disabled_away_state_image = os.path.join(images_dir, 'scan-button-small-disabled.png')
    mouse_over_state_image = os.path.join(images_dir, 'scan-button-small-hover.png')
    # mouse_disabled_over_state_image = os.path.join(images_dir, 'scan-button-small-hover-disabled.png')

    scan_data = {'Simulate uploading': True, 'Simulate modeling': True, 'Show images html': True,
                 'Show 3D model': True, 'cameras_list': cameras_list, 'usb_map_dict': usb_map_dict}
    #  Initialize all default configurations. These should be changeable in the "settings" panel
    while True:  # Event Loop
        # ##############################################################################################################
        #                                                                                                              #
        #                                START EVENT LOOP                                                              #
        #                                                                                                              #
        # ##############################################################################################################

        demo_dir = os.path.join(scans_dir, 'DEMO')
        Path(demo_dir).mkdir(parents=True, exist_ok=True)

        # initialize all status lists to empty:
        # scans_dict = {}

        scan_start_time = datetime.now()
        dt_string = scan_start_time.strftime("%d-%b-%Y %H:%M:%S")

        # ##############################################################################################################
        #                GET EVENT AND VALUES FROM WINDOW READ AND PROCESS EVENTS                                      #
        # ##############################################################################################################
        event, values = window.read()
        logging.debug(f'event={event}, {values}')
        if values:
            for key in values:
                scan_data[key] = values[key]

        scan_data['window'] = window

        if event == '-CAMERAS_LOADED-':
            cameras_list, usb_map_dict = values[event]
            scan_data['cameras_list'] = cameras_list
            scan_data['usb_map_dict'] = usb_map_dict
            # scans_dict[long_scan_id] = "-CAMERAS_LOADED-"
            window['_DATE_'].update(dt_string)
            window['_ACTION_STATUS_LINE_1_'].update("Ready to Scan.")
            window['_SCAN_BUTTON_'].update(image_filename=mouse_away_state_image)
            window['_ACTION_STATUS_LINE_2_'].update("Fill in details, then click SCAN to start.")
            window['_PROGRESS_BAR_'].update(0)
            window['_ACTION_STATUS_LINE_3_'].update(f"{len(cameras_list)} Cameras Found.")
            window['_SCAN_ID_'].update('')
            window.refresh()

        ################################################################################################################
        #          MOUSE ENTERS OR LEAVES SCAN BUTTON                                                                  #
        ################################################################################################################
        # Mouse Over and Mouse Away Scan button image toggling:

        if event == '_SCAN_BUTTON_+MOUSE AWAY+':
            logging.debug(f'\nEVENT PROCESSING FOR: {event}')
            if not scan_disabled_state:
                window['_SCAN_BUTTON_'].update(image_filename=mouse_away_state_image)
                window.Refresh()
                logging.debug(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '_SCAN_BUTTON_+MOUSE OVER+':
            logging.debug(f'\nEVENT PROCESSING FOR: {event}')
            if not scan_disabled_state:
                window['_SCAN_BUTTON_'].update(image_filename=mouse_over_state_image)
                logging.debug(f'EXIT EVENT PROCESSING FOR: {event}\n')
                window.Refresh()
            continue

        ################################################################################################################
        #          EXIT or WINDOW_CLOSED                                                                               #
        ################################################################################################################
        elif event in (None, 'Exit'):
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            terminate(0, 'User requested termination.')

        ################################################################################################################
        #          WIFI CONFIGURATION ICON CLICKED                                                                     #
        ################################################################################################################
        elif event == '_WIFI_ICON_':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            # ***************** WiFi Button pressed!  *****************************
            window.perform_long_operation(lambda: config_wifi(scan_data), '-END CONFIG WIFI-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END CONFIG_WIFI-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {values}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          SETTINGS ICON CLICKED                                                                               #
        ################################################################################################################
        elif event == '_SETTINGS_ICON_':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            # continue

            # ***************** Settings Button pressed!  *****************************
            # window.perform_long_operation(lambda: config_settings(scan_data), '-END SETTINGS-')
            settings_window = sg.Window('SonaScan Settings', settings_layout)
            window['_ACTION_STATUS_LINE_1_'].update("Editing Settings...")
            window.Refresh()
            while True:
                settings_event, settings_values = settings_window.read()
                print(settings_event, settings_values)
                if settings_event == sg.WIN_CLOSED or settings_event == 'Exit' or settings_event == 'Cancel':
                    settings_window.close()
                    continue

                elif settings_event == 'Submit':
                    [scan_data['simulate_uploading'],
                     scan_data['simulate_modeling'],
                     scan_data['show_images_html'],
                     scan_data['show_3D_model']] = settings_values
                    settings_window.close()

            # settings_window.close()
            # window.write_event_value('-END SETTINGS-', scan_data)
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END SETTINGS-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')

            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Settings Configured. Returned: {return_value}')
            # window.write_event_value('=SHOW IMAGES-', values)
            # window. '=SHOW IMAGES-'
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          INFO ICON CLICKED                                                                                   #
        ################################################################################################################
        elif event == '_INFO_ICON_':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            pass  # TODO:   ***************** Info Button pressed!  ************************************
            window['_ACTION_STATUS_LINE_1_'].update("Viewing Info...")
            window.Refresh()
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '_UPLOADS_ICON_':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            pass  # TODO: ***************** Uploads Icon Button pressed!  ************************
            window['_ACTION_STATUS_LINE_1_'].update("Viewing uploads waiting...")
            window.Refresh()
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          SCAN BUTTON PRESSED                                                                                 #
        ################################################################################################################
        elif event == '_SCAN_BUTTON_+LEFT CLICK+':
            # ############################## START GET_SCAN_ID AND MAKE DIR ###########################################
            logging.info(f'scanner_id = {scanner_id}')
            # scans_dict[long_scan_id] = "-READY_TO_SCAN-"
            window['_DATE_'].update(dt_string)
            window['_ACTION_STATUS_LINE_1_'].update("Scan Requested.")
            window['_SCAN_BUTTON_'].update(image_filename=mouse_away_state_image)
            window['_ACTION_STATUS_LINE_2_'].update("Scanning.")
            window['_PROGRESS_BAR_'].update(0)
            window['_ACTION_STATUS_LINE_3_'].update("")
            window['_SCAN_ID_'].update('')
            window.refresh()
            scan_id, long_scan_id, scan_dir = get_scan_id(scanner_id, scanner_dir)
            scan_data['scanner_id'] = scanner_id
            scan_data['scan_id'] = scan_id
            scan_data['long_scan_id'] = os.path.join(scanner_id, scan_id)
            scan_data['scan_dir'] = scan_dir
            window['_SCAN_ID_'].update(scan_id)
            try:
                os.makedirs(scan_dir, mode=770, exist_ok=True)
            except OSError as error:
                print("Directory '%s' can not be created", error)
            logging.info(f'scan_id = {scan_id}')
            # ############################## END GET_SCAN_ID AND MAKE DIR #############################################

            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT {event} TRIGGERS ASYNCHRONOUS LONG OPERATION: scan()')
            window.perform_long_operation(lambda:  scan(scan_data), '-END SCAN-')
            print(f'EXIT EVENT {event} LONG OPERATION scan() IS RUNNING ASYNCHRONOUS,\n')
            continue

        elif event == '-END SCAN-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            # return_value = values
            # window['_ACTION_STATUS_LINE_1_'].update(f'Scan completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          NO SCANNER FOUND. RUNNING DEMO                                                                      #
        ################################################################################################################
        elif event == 'DEMO':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            window.perform_long_operation(lambda: demo(scan_data), '-END DEMO-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END DEMO-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'DEMO Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          SHOW IMAGES                                                                                         #
        ################################################################################################################
        elif event == '-SHOW IMAGES-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            if scan_data['Show images html']:
                window.perform_long_operation(lambda: show_images(scan_data), '-END SHOW IMAGES-')
                print(f'EXIT EVENT PROCESSING FOR: {event}\n')
                continue

        elif event == '-END SHOW IMAGES-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          UPLOAD IMAGES                                                                                       #
        ################################################################################################################
        # elif event == '-UPLOAD IMAGES-':
        #    print(f'\nEVENT PROCESSING FOR: {event}')
        #    scan_data = values
        #    window.perform_long_operation(lambda: upload_images(scan_data), '-END UPLOAD IMAgES-')
        #    print(f' EXIT EVENT PROCESSING FOR: {event}\n')

        elif event == '-END UPLOAD IMAGES-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          GET PHOTOSCENE_ID                                                                                #
        ################################################################################################################
        elif event == '-GET PHOTOSCENE-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda: get_photoscene_id(scan_data), '-END GET PHOTOSCENE-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END GET PHOTOSCENE-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          ATTACH IMAGES TO PHOTOSCENE                                                                         #
        ################################################################################################################
        elif event == '-ATTACH IMAGES-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda: attach_images(scan_data), '-END ATTACH IMAGES-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END ATTACH IMAGES-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          ATTACH Ground Control Points (GCP.xml) TO PHOTOSCENE                                                #
        ################################################################################################################
        elif event == '-ATTACH GCP-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda:  attach_gcp(scan_data), '-END ATTACH GCP-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END ATTACH GCP-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          LAUNCH MODELING                                                                                     #
        ################################################################################################################
        elif event == '-LAUNCH MODELING-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda: launch_modeling(scan_data), '-END LAUNCH MODELING-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END LAUNCH MODELING-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          POLL FOR MODEL COMPLETION                                                                           #
        ################################################################################################################
        elif event == '-START POLLING-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda:  poll_for_completion(scan_data), '-END POLLING-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END POLLING-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          DOWNLOAD OBJ AND UNZIP                                                                              #
        ################################################################################################################
        elif event == '-START DOWNLOAD OBJ-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda:  download_obj(scan_data), '-END DOWNLOAD OBJ-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END DOWNLOAD OBJ-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          CROP OBJ                                                                                            #
        ################################################################################################################
        elif event == '-START CROP OBJ-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda:  crop_obj(scan_data), '-END CROP OBJ-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END CROP OBJ-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #          CONVERT OBJ TO STL                                                                                  #
        ################################################################################################################
        elif event == '-START CONVERT TO STL-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda: convert_obj_to_stl(scan_data), '-END CROP OBJ-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END CROP OBJ-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['-_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #         UPLOAD OBJS, STL, GCP, INDEX.HTML AND SCAN_DATA TO SONASERVER                                        #
        ################################################################################################################
        elif event == '-START UPLOAD OBJ AND STL-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda: upload_obj_and_stl(scan_data), '-END UPLOAD OBJ AND STL-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END UPLOAD OBJ AND STL-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #         SEND CONFIRMATION EMAILS                                                                             #
        ################################################################################################################
        elif event == '-START SEND EMAILS-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda: send_emails(scan_data), '-END SEND EMAILS-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END SEND EMAILS-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        ################################################################################################################
        #         SHOW 3D MODEL                                                                                        #
        ################################################################################################################
        elif event == '-START SHOW MODEL-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            scan_data = values
            window.perform_long_operation(lambda: show_model(scan_data), '-END SHOW MODEL-')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        elif event == '-END SHOW MODEL-':
            print(f'\nevent={event}, {values}\n')
            print(f'\nEVENT PROCESSING FOR: {event}')
            return_value = values
            window['_ACTION_STATUS_LINE_1_'].update(f'Completed. Returned: {return_value}')
            print(f'EXIT EVENT PROCESSING FOR: {event}\n')
            continue

        else:
            print(f'\nAT END OF EVENT LOOP. FOUND EVENT={event}\n')
    ################################################################################################################
    #         END OF GUI EVENT LOOP                                                                                #
    ################################################################################################################


if __name__ == '__main__':
    main()
