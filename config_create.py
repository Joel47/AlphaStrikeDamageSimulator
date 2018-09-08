import argparse
import logging
import json
import os

settings = {
    'base_config': 'config.json',
    'new_config': 'config_pv.json',
    'pv': 20,
    'attacker_list': 'unit_lists/xotl_skill4.json',
    'defender_list':  'unit_lists/xotl_skill3.json',
    'limit_specials': False,  # Not yet supported
    'supported_specials': ['RFA', 'SHLD', 'AMS', 'RAMS', 'ARM', 'CR', 'CASE', 'CASEII',
                           'BHJ2', 'BHJ3', 'RHS', 'STL', 'ENE', 'LG', 'VLG', 'SLG'],
    'debug': False
}


def settings_get_from_command_line():
    parser = argparse.ArgumentParser()
    for argument in settings:
        if isinstance(settings[argument], bool):
            parser.add_argument('--' + argument, action="store_true")
        elif isinstance(settings[argument], int):
            parser.add_argument('--' + argument, type=int)
        elif isinstance(settings[argument], float):
            parser.add_argument('--' + argument, type=float)
        elif isinstance(settings[argument], list):
            parser.add_argument('--' + argument, action="append")
        else:
            parser.add_argument('--' + argument)
    args = parser.parse_args()
    for arg in vars(args):
        if getattr(args, arg) is not None:
            if getattr(args, arg):
                settings[arg] = getattr(args, arg)


def logging_configure(debug=False):
    if debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    log_format = '%(message)s'
    logging.basicConfig(level=log_level, format=log_format)


def config_read(config_file):
    with open(config_file) as json_data:
        units = json_load_byteified(json_data)
    logging.debug('Reading config ' + config_file)
    return units


def json_load_byteified(file_handle):
    return _byteify(
        json.load(file_handle, object_hook=_byteify),
        ignore_dicts=True
    )


def json_loads_byteified(json_text):
    return _byteify(
        json.loads(json_text, object_hook=_byteify),
        ignore_dicts=True
    )


def _byteify(data, ignore_dicts=False):
    # if this is a unicode string, return its string representation
    if isinstance(data, unicode):
        return data.encode('utf-8')
    # if this is a list of values, return list of byteified values
    if isinstance(data, list):
        return [_byteify(item, ignore_dicts=True) for item in data]
    # if this is a dictionary, return dictionary of byteified keys and values
    # but only if we haven't already byteified it
    if isinstance(data, dict) and not ignore_dicts:
        return {
            _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True)
            for key, value in data.iteritems()
        }
    # if it's anything else, return it in its original form
    return data


def config_write(config, file_path):
    with open(file_path, 'w') as outfile:
        json.dump(config, outfile, sort_keys=True, indent=4)


def unit_list_get(unit_file):
    unit_data = config_read(unit_file)
    unit_list = []
    for unit in unit_data:
        if unit['points'] == settings['pv']:
            if settings['limit_specials']:
                # TODO - support this
                pass
            unit_list.append(unit['name'])
    return unit_list


if __name__ == "__main__":
    settings_get_from_command_line()
    logging_configure(settings['debug'])
    base_config = config_read(settings['base_config'])
    base_config['attacker_list'] = unit_list_get(settings['attacker_list'])
    base_config['defender_list'] = unit_list_get(settings['defender_list'])
    if settings['new_config'] is None:
        settings['new_config'] = os.path.splitext(settings['base_config'])[0] + str(settings['pv']) + \
                                 os.path.splitext(settings['base_config'])[1]
    config_write(base_config, settings['new_config'])
