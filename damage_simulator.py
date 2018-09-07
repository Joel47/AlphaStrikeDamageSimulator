import logging
import os
import shutil
import random
import csv
import json
import argparse
import sys

__version__ = 1.8
CONFIG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.json')

# Constants for use below
MAX_ROUNDS = 100  # Avoid runaways

SHORT_RANGE = 0
MEDIUM_RANGE = 1
LONG_RANGE = 2

# Range algorithms
RANDOM_RANGE = -1
FAST_UNIT_CAUSES_SLOW_APPROACH = -2
INITIATIVE_HELPS_FASTER_MINIMIZE_HIT_CHANCE = -3
INITIATIVE_HELPS_FASTER_MAXIMIZE_DAMAGE = -4
FAST_UNIT_MINIMIZES_DAMAGE = -5

# Unit types
MECH = 0
VEHICLE = 1
PROTOMECH = 2
INFANTRY = 3
BATTLEARMOR = 4

# Motive types
TRACKED = 0
NAVAL = 1
WHEELED = 2
HOVER = 3
VTOL = 4
WIGE = 5

# Attacker/Defender
ATTACKER = 0
DEFENDER = 0


config = {
    "unit_list_path": 'unit_lists/synthetic.json',
    "attacker": None,
    "defender": None,
    "attacker_list": [],
    "defender_list": [],
    "log_level": 30,
    "log_file": "",
    "battle_runs": 1000,
    "csv": {
        "output": False,
        "path": "c:/temp/alphastrike.csv"
    },
    "bbcode": {
        "output": False,
        "path": "c:/temp/alphastrike.txt"
    },
    "max_tolerable_heat": 1,
    "range_determination": "random",
    "woods_percent": {
        "short": 10,
        "medium": 30,
        "long": 50
    },
    "cover_percent": {
        "short": 10,
        "medium": 30,
        "long": 50
    }
}


class CombatUnit(object):

    def __init__(self, name, unit_type=MECH, armor=1, structure=1, weapons=[0,0,0], movement=0, skill=4,
                 motive_type=0, jump=None, special=[]):
        self.name = name
        self.type = unit_type
        self.armor = armor
        self.armor_original = armor
        self.structure = structure
        self.structure_original = structure
        self.weapons = list(weapons)
        self.movement = movement
        self.motive_type = motive_type
        self.jump = jump
        self.skill = skill
        if not (special is None):
            self.special = list(special)
        else:
            self.special = []
        self.crits = []
        self.heat = 0

    def effective_skill(self):
        misc_bonuses = 0
        if 'SHLD' in self.special:
            misc_bonuses += 1
        if self.jump is not None:
            if self.jump > self.movement:
                misc_bonuses += 2
        return self.skill + self.heat + misc_bonuses

    def effective_movement(self):
        # Does NOT include jump
        return max(0, self.movement - (self.heat * 2))

    def movement_mod(self):
        other_mods = 0
        for sa in self.special:
            if sa == 'LG' or sa == 'VLG' or sa == 'SLG':
                other_mods -= 1
        if self.type == PROTOMECH or self.type == BATTLEARMOR:
            other_mods += 1
        move_mod = movement_mod(self.effective_movement())
        if self.jump is not None:
            if self.jump > self.movement:
                move_mod = movement_mod(self.jump) + 1
        return move_mod + other_mods

    def damage_apply(self, damage, attack_range=SHORT_RANGE, attacker_specials='', is_area_effect=False):
        logging.debug('Applying ' + str(damage) + ' damage to ' + self.name)
        heat_added = 0
        if damage > 0:
            # Check for HT#/#/#
            for sa in attacker_specials:
                if len(sa) >= 7:
                    if sa[:2] == 'HT':
                        heat_text = sa[2:]
                        heat_array = heat_text.split('/')
                        try:
                            heat_added = int(heat_array[attack_range])
                        except BaseException as why:
                            logging.error('Error getting HT number: ' + str(why))
        if 'RFA' in self.special:
            if 'ENE' in attacker_specials:
                logging.debug('Reflective Armor reduces damage by half.')
                damage = divide_by_two_round_up(damage)
                heat_added = divide_by_two_round_up(heat_added)
            elif heat_added > 0:
                heat_added = divide_by_two_round_up(heat_added)
                damage = max(0, damage - heat_added)
        if 'SHLD' in self.special:
            if not is_area_effect:
                logging.debug('SHLD prevents 1 point of damage.')
                damage = max(0, damage - 1)
        if 'AMS' in self.special or 'RAMS' in self.special:
            ams_active = False
            for special in attacker_specials:
                if special[:3] == 'LRM' or special[:3] == 'SRM' or special[:2] == 'IF':
                    ams_active = True
            if ams_active:
                logging.debug('AMS prevents 1 point of damage.')
                damage = max(0, damage - 1)
        if heat_added > 0 and self.type != MECH:
            # Not a heat-tracking unit; added HT to Damage
            damage += heat_added
            heat_added = 0
        if damage <= self.armor:
            self.armor -= damage
            logging.debug(str(damage) + ' applied to armor; ' + str(self.armor) + ' armor remaining.')
        else:
            if self.armor > 0:
                # Don't want to see this message unless there was armor before the hit.
                logging.debug('Armor destroyed.')
            damage -= self.armor
            self.armor = 0
            if damage < self.structure:
                self.structure -= damage
                logging.debug(str(damage) + ' applied to structure; ' + str(self.structure) + ' structure remaining.')
                self.apply_crit(two_d6())
            else:
                self.structure = 0
                logging.info('Unit ' + self.name + ' destroyed.')
        if self.structure > 0 and self.type == MECH and heat_added > 0:
            # Add heat, but not more than 2
            self.heat_apply(min(heat_added, 2))

    def heat_apply(self, heat):
        if self.type == MECH:
            self.heat += heat
            logging.debug(self.name + ' new heat: ' + str(self.heat))
            return self.heat
        else:
            logging.error('Tried to add heat to a non-heat-tracking unit.')
            return 0

    def heat_remove(self):
        if self.type == MECH and self.structure > 0:
            logging.debug(self.name + ' cooling off.')
            self.heat = 0

    def motive_check(self):
        if self.type == VEHICLE:
            motive_roll = two_d6()
            if self.motive_type == WHEELED or self.motive_type == HOVER:
                motive_roll += 1
            elif self.motive_type == VTOL or self.motive_type == WIGE:
                motive_roll += 2
            if motive_roll == 9 or motive_roll == 10:
                self.movement = max(0, self.movement - 2)
                logging.info(self.name + ' Motive hit: movement reduced to ' + str(self.movement))
            elif motive_roll == 11:
                movement_loss = divide_by_two_round_up(self.movement)
                self.movement -= movement_loss
                logging.info(self.name + 'Motive hit: movement reduced to ' + str(self.movement))
            elif motive_roll == 12:
                self.movement = 0
                logging.info(self.name + 'Motive hit: movement reduced to 0')
            else:
                logging.debug('Motive hit: No effect.')

    def apply_crit(self, crit_roll):
        for sa in self.special:
            if sa == 'ARM':
                logging.debug('Armored Component: ignoring crit, and crossing off ARM.')
                self.special.remove('ARM')
                return
        if 'CR' in self.special:
            logging.debug('Critical Resistant: -2 to crit roll')
            crit_roll -= 2
        if self.type == MECH:
            if crit_roll == 2:
                logging.debug('Ammo Explosion!')
                if 'ENE' in self.special or 'CASEII' in self.special:
                    logging.debug('Ignored due to ENE special.')
                elif 'CASE' in self .special:
                    logging.debug('CASE. Appling 1 extra damage.')
                    self.damage_apply(1)
                else:
                    logging.debug('Unit destroyed.')
                    self.structure = 0
            elif crit_roll == 3 or crit_roll == 11:
                logging.debug('Engine hit')
                if 'Engine hit' in self.crits:
                    logging.debug('Second engine hit; unit destroyed.')
                    self.structure = 0
                else:
                    self.crits.append('Engine hit')
            elif crit_roll == 4 or crit_roll == 10:
                logging.debug('Fire Control hit')
                self.skill += 2
            elif crit_roll == 6 or crit_roll == 8:
                logging.debug('Weapon hit')
                for range_band in [0, 1, 2]:
                    self.weapons[range_band] = max(0, self.weapons[range_band] - 1)
                logging.debug('Weapons now ' + str(self.weapons))
            elif crit_roll == 7:
                logging.debug('MP Hit')
                movement_loss = max(2, divide_by_two_round_up(self.movement))
                self.movement = max(0, self.movement - movement_loss)
                logging.debug('New movement mod: ' + str(self.movement_mod()))
            elif crit_roll == 12:
                logging.debug('Unit destroyed.')
                self.structure = 0
            else:
                logging.debug('No crit.')
        elif self.type == VEHICLE:
            if crit_roll == 2:
                logging.debug('Ammo Explosion!')
                if 'ENE' in self.special or 'CASEII' in self.special:
                    logging.debug('Ignored due to ENE special.')
                elif 'CASE' in self .special:
                    logging.debug('CASE. Appling 1 extra damage.')
                    self.damage_apply(1)
                else:
                    logging.debug('Unit destroyed.')
                    self.structure = 0
            elif crit_roll == 3:
                logging.debug('Crew Stunned')
                self.crits.append('Crew Stunned')
            elif crit_roll == 4 or crit_roll == 5:
                logging.debug('Fire Control hit')
                self.skill += 2
            elif crit_roll == 9 or crit_roll == 10:
                logging.debug('Weapon hit')
                for range_band in [0, 1, 2]:
                    self.weapons[range_band] = max(0, self.weapons[range_band] - 1)
                logging.debug('Weapons now ' + str(self.weapons))
            elif crit_roll == 11:
                logging.debug('Crew killed!')
                self.structure = 0
            elif crit_roll == 12:
                logging.debug('Engine Hit.')
                if 'Engine Hit' in self.crits:
                    logging.debug('Second hit; vehicle destroyed.')
                    self.structure = 0
                else:
                    self.crits.append('Engine Hit')
                    self.movement = divide_by_two_round_up(self.movement)
                    logging.debug('New movement mod: ' + str(self.movement_mod()))
                    for range_band in [0, 1, 2]:
                        self.weapons[range_band] = divide_by_two_round_up(self.weapons[range_band])
            else:
                logging.debug('No crit.')
        elif self.type == PROTOMECH:
            logging.debug('Crits not yet implemented for Protomechs')
            # TODO - implement protomech crits

    def crit_clear(self):
        for crit in self.crits[:]:
            if crit in ['Crew Stunned']:
                self.crits.remove(crit)
                logging.debug('Crit expired: ' + crit)

    def state_log(self):
        logging.debug(self.name + ': ' + str(self.armor) + '/' + str(self.structure) + ' ' +
                      str(self.weapons) + ' SA:' + str(self.special) + ' Crits:' + str(self.crits) +
                      ' HT:' + str(self.heat))

    def round_complete(self):
        self.crit_clear()
        if 'BHJ2' in self.special:
            if self.armor > 0:
                self.armor = max(self.armor_original, self.armor + 1)
                logging.debug('Using BHJ2 to restore 1 point of armor.')
        elif 'BHJ3' in self.special:
            if self.armor > 0:
                self.armor = max(self.armor_original, self.armor + 2)
                logging.debug('Using BHJ3 to restore 2 points of armor.')
        if 'RHS' in self.special and self.heat > 0:
            logging.debug('Using RHS to cool down.')
            self.heat -= 1
            if random.randint(1, 6) == 1:
                logging.info('RHS check rolled a 1. Disabling RHS.')
                self.special.remove('RHS')


def unit_create_from_dict(stat_dict):
    # name, type, armor, structure, weapons, movement, skill, motive_type=0, special=None
    try:
        unit_name = stat_dict['name']
    except KeyError:
        unit_name = 'No name'
    try:
        unit_type = stat_dict['type']
    except KeyError:
        unit_type = MECH
    try:
        unit_armor = stat_dict['armor']
    except KeyError:
        unit_armor = 0
    try:
        unit_structure = stat_dict['structure']
    except KeyError:
        unit_structure = 1
    try:
        unit_weapons = []
        for range_band in [0, 1, 2]:
            unit_weapons.append(stat_dict['weapons'][range_band])
        # TODO - verify this is a list with 3 entries
    except KeyError:
        logging.error('Error setting weapon information for ' + unit_name)
        unit_weapons = [0, 0, 0]
    try:
        unit_move = stat_dict['move']
    except KeyError:
        logging.error('Error setting move for ' + unit_name)
        unit_move = 0
    try:
        unit_skill = stat_dict['skill']
    except KeyError:
        unit_skill = 4
    try:
        unit_motive = stat_dict['motive']
    except KeyError:
        unit_motive = 0
    try:
        unit_jump = stat_dict['jump']
    except KeyError:
        unit_jump = None
    try:
        unit_special = stat_dict['special']
    except KeyError:
        unit_special = []
    return CombatUnit(unit_name, unit_type, unit_armor, unit_structure, unit_weapons, unit_move, unit_skill,
                      unit_motive, jump=unit_jump, special=unit_special)


def unit_list_read_from_json(json_path):
    with open(json_path) as json_data:
        units = json_load_byteified(json_data)
    logging.debug('Reading unit list ' + json_path)
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


def movement_mod(movement, jumped=False):
    if jumped:
        jump_mod = 1
    else:
        jump_mod = 0
    if movement == 0 and not jumped:
        return -4
    elif movement < 5:
        return 0 + jump_mod
    elif movement < 9:
        return 1 + jump_mod
    elif movement < 13:
        return 2 + jump_mod
    elif movement < 19:
        return 3 + jump_mod
    elif movement < 35:
        return 4 + jump_mod
    else:
        return 5 + jump_mod


def divide_by_two_round_up(x):
    return int(round(float(x)/2))


def logging_configure(log_path='', log_level=10):
    if len(log_path) > 0:
        log_to_file = True
        output_log_file_directory = os.path.dirname(log_path) + '/'
        output_log_file_name = os.path.basename(log_path)
    else:
        # Log to screen
        log_to_file = False
        output_log_file_directory = ''
        output_log_file_name = ''
    if log_level <= 10:  # Debug
        log_level = logging.DEBUG
    elif log_level <= 20:  # Info
        log_level = logging.INFO
    else:
        log_level = logging.WARNING
    log_format = '%(message)s'
    if log_to_file:
        try:
            if not os.path.isdir(output_log_file_directory):
                os.makedirs(output_log_file_directory)
        except BaseException as log_error:
            raise IOError('Unable to create log folder: ' + str(log_error))
        # Check for existing log file and rename if it exists
        if os.path.isfile(output_log_file_directory + output_log_file_name):
            file_increment = 1
            while os.path.isfile(output_log_file_directory + output_log_file_name + '_' + str(file_increment)):
                file_increment += 1
            try:
                shutil.move(output_log_file_directory + output_log_file_name, output_log_file_directory +
                            output_log_file_name + '_' + str(file_increment))
            except BaseException as log_error:
                raise RuntimeError('Unable to copy old output log.  Stopping so as not to overwrite data. '
                                   + str(log_error))
        logging.basicConfig(filename=output_log_file_directory + output_log_file_name, level=log_level,
                            format=log_format)
    else:
        logging.basicConfig(level=log_level, format=log_format)


def two_d6():
    die1 = random.randint(1, 6)
    die2 = random.randint(1, 6)
    return die1 + die2


def dice_test(times_to_roll):
    dice_results = []
    for roll in range(2, 13):
        dice_results.append(0)
    for roll in range(0, times_to_roll):
        result = two_d6()
        dice_results[result - 2] += 1
    logging.critical('Dice results:')
    for roll in range(2, 13):
        logging.critical(str(roll) + ': ' + str(dice_results[roll - 2]))


def roll_to_hit(skill, range_mod, def_mod, terrain=0):
    target_number = skill + range_mod + def_mod + terrain
    die_roll = two_d6()
    if die_roll >= target_number:
        logging.debug('Hit! (Needed ' + str(target_number) + ', rolled ' + str(die_roll) + ')')
        return True
    else:
        logging.debug('Miss! (Needed ' + str(target_number) + ', rolled ' + str(die_roll) + ')')
        return False


def probability_to_hit(target_number):
    if target_number <= 2:
        return 1
    elif target_number == 3:
        return 0.9722
    elif target_number == 4:
        return 0.9166
    elif target_number == 5:
        return 0.8333
    elif target_number == 6:
        return 0.7222
    elif target_number == 7:
        return 0.5833
    elif target_number == 8:
        return 0.4166
    elif target_number == 9:
        return 0.2777
    elif target_number == 10:
        return 0.1666
    elif target_number == 11:
        return 0.0833
    elif target_number == 12:
        return 0.0277
    else:
        return 0


def average_damage(base_damage, target_number):
    return float(base_damage) * probability_to_hit(target_number)


def range_for_least_defender_damage(attacker, defender):
    # set "minimum damage" to 100 for all range bands, since that's much higher than any unit can have
    attacker_damage = [100, 100, 100]
    for attacker_range in [SHORT_RANGE, MEDIUM_RANGE, LONG_RANGE]:
        if defender.weapons[attacker_range] > 0:
            # Only check if the defender can shoot back
            target_number = attacker.effective_skill() + (2 * attacker_range) + defender.movement_mod()
            attacker_damage[attacker_range] = average_damage(defender.weapons[attacker_range], target_number)
    if attacker_damage[SHORT_RANGE] < attacker_damage[MEDIUM_RANGE]:
        if attacker_damage[SHORT_RANGE] < attacker_damage[LONG_RANGE]:
            logging.debug('Best range for defender is short. '
                          'Expected received damage = ' + str(round(attacker_damage[SHORT_RANGE], 2)))
            return SHORT_RANGE
        else:
            logging.debug('Best range for defender is long. '
                          'Expected received damage = ' + str(round(attacker_damage[LONG_RANGE], 2)))
            return LONG_RANGE
    else:
        if attacker_damage[MEDIUM_RANGE] < attacker_damage[LONG_RANGE]:
            logging.debug('Best range for defender is medium. '
                          'Expected received damage = ' + str(round(attacker_damage[MEDIUM_RANGE], 2)))
            return MEDIUM_RANGE
        else:
            logging.debug('Best range for defender is long. '
                          'Expected received damage = ' + str(round(attacker_damage[LONG_RANGE], 2)))
            return LONG_RANGE


def range_get(range_algorithm, current_round, range_previous, unit_1, unit_2):
    if unit_1.movement == 0 and unit_2.movement == 0:
        return range_previous
    if range_algorithm == SHORT_RANGE:
        return SHORT_RANGE
    elif range_algorithm == MEDIUM_RANGE:
        return MEDIUM_RANGE
    elif range_algorithm == LONG_RANGE:
        return MEDIUM_RANGE
    elif range_algorithm == RANDOM_RANGE:
        # Randomly choose between short and medium range
        range_roll = random.randint(1, 100)
        if range_roll <= 10:
            return SHORT_RANGE
        elif range_roll <= 70:
            return MEDIUM_RANGE
        else:
            return LONG_RANGE
    elif range_algorithm == FAST_UNIT_CAUSES_SLOW_APPROACH:
        if unit_1.movement > unit_2.movement:
            faster_unit = unit_1
            slower_unit = unit_2
        else:
            faster_unit = unit_2
            slower_unit = unit_1
        speed_difference = abs(unit_1.movement - unit_2.movement)
        if speed_difference == 0:
            logging.debug('Range calc: No speed difference; stick to long range for first 2 rounds, then medium.')
            if current_round <= 2:
                return LONG_RANGE
            else:
                return MEDIUM_RANGE
        elif slower_unit.movement == 0:
            logging.debug('Range calc: Slower unit immobilized. '
                          'Faster unit picks longest range at which it can deal damage.')
            if faster_unit.weapons[LONG_RANGE] > 0:
                return LONG_RANGE
            elif faster_unit.weapons[MEDIUM_RANGE] > 0:
                return MEDIUM_RANGE
            else:
                return SHORT_RANGE
        elif current_round < 36/slower_unit.movement:
            logging.debug('Range calc: On approach. Longest range at which faster unit has weapons.')
            if faster_unit.weapons[LONG_RANGE] > 0:
                return LONG_RANGE
            elif faster_unit.weapons[MEDIUM_RANGE] > 0:
                return MEDIUM_RANGE
            else:
                return SHORT_RANGE
        else:
            logging.debug('Range calc: Dueling. '
                          'Assuming faster unit can remain at medium range (or short if it has no medium damage).')
            if faster_unit.weapons[MEDIUM_RANGE] > 0:
                return MEDIUM_RANGE
            else:
                return SHORT_RANGE
    elif range_algorithm == FAST_UNIT_MINIMIZES_DAMAGE:
        if unit_1.movement > unit_2.movement:
            faster_unit = unit_1
            slower_unit = unit_2
        else:
            faster_unit = unit_2
            slower_unit = unit_1
        speed_difference = abs(unit_1.movement - unit_2.movement)
        if speed_difference == 0:
            logging.debug('Range calc: No speed difference; stick to long range for first 2 rounds, then medium.')
            if current_round <= 2:
                return LONG_RANGE
            else:
                return MEDIUM_RANGE
        elif slower_unit.movement == 0:
            logging.debug('Range calc: Slower unit immobilized. '
                          'Faster unit picks range to minimize incoming damage.')
            return range_for_least_defender_damage(slower_unit, faster_unit)
        elif current_round == 1:
            if faster_unit.weapons[LONG_RANGE] > 0 or slower_unit.weapons[LONG_RANGE] > 0:
                logging.debug('Range calc: First round - long range.')
                return LONG_RANGE
            else:
                logging.debug('Range calc: First round - no long range weapons on either side, so start at medium.')
                return MEDIUM_RANGE
        else:
            logging.debug('Range calc: Dueling. '
                          'Faster unit picks range to minimize incoming damage.')
            return range_for_least_defender_damage(slower_unit, faster_unit)


def woods_mod_calc(range_band, woods_percentages):
    if range_band == SHORT_RANGE:
        woods_percent = woods_percentages['short']
    elif range_band == MEDIUM_RANGE:
        woods_percent = woods_percentages['medium']
    elif range_band == LONG_RANGE:
        woods_percent = woods_percentages['long']
    else:
        logging.warning('Bad range band in woods_get. Setting to short.')
        woods_percent = woods_percentages['short']
    if random.random() * 100 < woods_percent:
        return 2
    else:
        return 0


def cover_mod_calc(range_band, cover_percentages):
    if range_band == SHORT_RANGE:
        cover_percent = cover_percentages['short']
    elif range_band == MEDIUM_RANGE:
        cover_percent = cover_percentages['medium']
    elif range_band == LONG_RANGE:
        cover_percent = cover_percentages['long']
    else:
        logging.warning('Bad range band in cover. Setting to short.')
        cover_percent = cover_percentages['short']
    if random.random() * 100 < cover_percent:
        return 2
    else:
        return 0


def range_algorithm_from_text(range_algorithm_description):
    if range_algorithm_description == 'fixed_short':
        range_determination_method = SHORT_RANGE
    elif range_algorithm_description == 'fixed_medium':
        range_determination_method = MEDIUM_RANGE
    elif range_algorithm_description == 'fixed_long':
        range_determination_method = LONG_RANGE
    elif range_algorithm_description == 'random':
        range_determination_method = RANDOM_RANGE
    elif range_algorithm_description == 'fast_unit_causes_slow_approach':
        range_determination_method = FAST_UNIT_CAUSES_SLOW_APPROACH
    elif range_algorithm_description == 'fast_unit_minimizes_damage':
        range_determination_method = FAST_UNIT_MINIMIZES_DAMAGE
    # TODO - range_determination = initiative_helps_faster_minimize_hit_chance  ***NOT YET IMPLEMENTED***
    # TODO - range_determination = initiative_helps_faster_maximize_damage  ***NOT YET IMPLEMENTED***
    else:
        logging.warning('Undefined range determination option: ' + range_algorithm_description + '; setting to short.')
        range_determination_method = SHORT_RANGE
    return range_determination_method


def one_vs_one(first_unit, second_unit):
    round_count = 0
    range_algorithm = range_algorithm_from_text(config['range_determination'])
    range_previous = LONG_RANGE
    while first_unit.structure > 0 and second_unit.structure > 0:
        round_count += 1
        logging.debug('========== ROUND ' + str(round_count) + ' ==========')
        range_band = range_get(range_algorithm, round_count, range_previous, first_unit, second_unit)
        range_mod = 2 * range_band
        range_previous = range_band
        woods_mod = woods_mod_calc(range_band, config['woods_percent'])
        first_unit_cover_mod = cover_mod_calc(range_band, config['cover_percent'])
        second_unit_cover_mod = cover_mod_calc(range_band, config['cover_percent'])
        if first_unit.heat <= int(config['max_tolerable_heat']):
            # Compute first unit mods and roll to hit
            if first_unit.movement_mod() == 0:
                first_unit_mods = -1
            else:
                first_unit_mods = 0
            if 'STL' in second_unit.special:
                first_unit_mods += int(float(range_mod) / 2)
            logging.debug(first_unit.name + ' shoots ' + second_unit.name)
            second_unit_was_hit = roll_to_hit(first_unit.effective_skill() + first_unit_mods,
                                              range_mod,
                                              second_unit.movement_mod(),
                                              terrain=woods_mod + second_unit_cover_mod)
            first_unit_fired = True
        else:
            logging.debug(first_unit.name + ' overheated; does not fire.')
            first_unit_fired = False
            second_unit_was_hit = False
        if second_unit.heat <= int(config['max_tolerable_heat']):
            # Compute second unit mods and roll to hit
            if second_unit.movement_mod() == 0:
                second_unit_mods = -1
            else:
                second_unit_mods = 0
            if 'STL' in first_unit.special:
                second_unit_mods += int(float(range_mod) / 2)
            logging.debug(second_unit.name + ' shoots ' + first_unit.name)
            first_unit_was_hit = roll_to_hit(second_unit.effective_skill() + second_unit_mods,
                                             range_mod,
                                             first_unit.movement_mod(),
                                             terrain=woods_mod + first_unit_cover_mod)
            second_unit_fired = True
        else:
            logging.debug(first_unit.name + ' overheated; does not fire.')
            second_unit_fired = False
            first_unit_was_hit = False
        first_unit_weapons = int(first_unit.weapons[range_band])
        second_unit_weapons = int(second_unit.weapons[range_band])
        if first_unit_was_hit:
            first_unit.motive_check()
            first_unit.damage_apply(second_unit_weapons, attack_range=range_band, attacker_specials=second_unit.special)
        if second_unit_was_hit:
            second_unit.motive_check()
            second_unit.damage_apply(first_unit_weapons, attack_range=range_band, attacker_specials=first_unit.special)
        # End Phase
        if first_unit_fired and ('Engine hit' in first_unit.crits):
            first_unit.heat_apply(1)
        elif not first_unit_fired:
            first_unit.heat_remove()
        if second_unit_fired and ('Engine hit' in second_unit.crits):
            second_unit.heat_apply(1)
        elif not second_unit_fired:
            second_unit.heat_remove()
        first_unit.round_complete()
        second_unit.round_complete()
        first_unit.state_log()
        second_unit.state_log()
        if round_count > MAX_ROUNDS:
            logging.info('Maximum rounds exceeded; calling the battle.')
            break
    if first_unit.structure > 0 and second_unit.structure > 0:
        logging.info('Draw.')
        logging.info('Both units survived.')
        winner = 0
    elif first_unit.structure <= 0 and second_unit.structure <= 0:
        logging.info('Draw.')
        winner = 0
    elif second_unit.structure > 0:
        logging.info('Winner: ' + second_unit.name)
        winner = 2
    elif first_unit.structure > 0:
        logging.info('Winner: ' + first_unit.name)
        winner = 1
    else:
        logging.error('Unsupported game end state.')
        winner = 0
    return {'winner': winner, 'rounds': round_count}


def config_set_from_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=CONFIG_FILE,
                        help='JSON file that will override settings in script, but be overridden by command line',
                        dest='config_file')
    parser.add_argument('--config_print', help='Display all configuration options with their current setting',
                        action="store_true")
    for argument in config:
        if isinstance(config[argument], bool):
            parser.add_argument('--' + argument, action="store_true")
        elif isinstance(config[argument], int):
            parser.add_argument('--' + argument, type=int)
        elif isinstance(config[argument], float):
            parser.add_argument('--' + argument, type=float)
        elif isinstance(config[argument], list):
            parser.add_argument('--' + argument, action="append")
        else:
            parser.add_argument('--' + argument)
    try:
        args = parser.parse_args()
    except BaseException as why:
        if str(why) != '0':
            print('Command line error: ' + str(why))
            try:
                print(parser.print_help())
            except BaseException as print_error:
                print('Parser error: ' + str(print_error))
        sys.exit(1)
    if args.config_file is not None:
        json_path = args.config_file
    if json_path is not None:
        # Read JSON file, overwrite default config values with anything found & add new params
        if not os.path.isfile(json_path):
            raise IOError('Missing config file at ' + json_path)
        with open(json_path, 'r+') as user_data:
            try:
                config_data = json.load(user_data)
            except BaseException as why:
                raise IOError('Error loading config file ' + json_path + ': ' + str(why))
        for config_setting in config_data:
            setting = config_setting.decode('utf-8')
            if isinstance(config_data[setting], basestring):
                config[setting] = config_data[config_setting].decode('utf-8')
            elif isinstance(config_data[setting], list):
                new_list = []
                for list_item in config_data[setting]:
                    if isinstance(list_item, basestring):
                        new_list.append(list_item.decode('utf-8'))
                    else:
                        new_list.append(list_item)
                config[setting] = list(new_list)
            else:
                config[setting] = config_data[config_setting]
    # Read command line, overwrite default config values with anything found & add new params
    for arg in vars(args):
        if getattr(args, arg) is not None:
            if getattr(args, arg):
                config[arg] = getattr(args, arg)
    if args.config_print:
        config_print()


def config_print(setting=None):
    if setting is not None:
        try:
            print(str(config[setting]))
        except:
            print('No config option "' + setting + '"')
    else:
        for option in config:
            print option + ': ' + str(config[option])


def unit_list_fight(unit_list):
    if config['csv']['output']:
        try:
            output_file_csv = open(config['csv']['path'], 'wb')
        except BaseException as why:
            logging.error('Failed to open CSV file ' + config['csv']['path'] + ' - ' + str(why))
            config['csv']['output'] = False
    if config['bbcode']['output']:
        try:
            output_file_bbcode = open(config['bbcode']['path'], 'wb')
        except BaseException as why:
            logging.error('Failed to open BBCode file ' + config['bbcode']['path'] + ' - ' + str(why))
            config['bbcode']['output'] = False
    defender_list = []
    completed_attackers = []
    if config['bbcode']['output']:
        output_file_bbcode.write('[table][tr][td]Attacker \ Defender[/td]')
    if config['csv']['output']:
        csv_fields = ['Attacker']
    for defender in unit_list:
        defender_list.append(defender)
        if config['bbcode']['output']:
            output_file_bbcode.write('[td][b]' + defender['name'] + ' (Skill ' + str(defender['skill']) + ')[/b][/td]')
        if config['csv']['output']:
            csv_fields.append(defender['name'])
    if config['bbcode']['output']:
        output_file_bbcode.write('[/tr]')
    if config['csv']['output']:
        csv_writer = csv.DictWriter(output_file_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL,
                                    fieldnames=csv_fields)
        csv_writer.writeheader()
    for attacker in unit_list:
        if config['bbcode']['output']:
            output_file_bbcode.write('[tr][td][b]' + attacker['name'] + ' (Skill ' + str(attacker['skill']) + ')[/b][/td]')
        if config['csv']['output']:
            csv_line = {'Attacker': attacker['name']}
        for defender in defender_list:
            if attacker['name'] == defender['name']:
                logging.debug('Identical units; skipping.')
                if config['bbcode']['output']:
                    output_file_bbcode.write('[td]-----[/td]')
                if config['csv']['output']:
                    csv_line[defender['name']] = 'N/A'
                continue
            if attacker['name'] in completed_attackers:
                # TODO - this isn't working
                logging.debug('Pairing already run; skipping.')
                if config['bbcode']['output']:
                    output_file_bbcode.write('[td]-----[/td]')
                if config['csv']['output']:
                    csv_line[defender['name']] = 'N/A'
                continue
            wins = [0, 0, 0]  # Ties, Attacker, Defender
            rounds = 0
            for battle in range(0, int(config['battle_runs'])):
                attacking_unit = unit_create_from_dict(attacker)
                defending_unit = unit_create_from_dict(defender)
                result_dict = one_vs_one(attacking_unit, defending_unit)
                wins[result_dict['winner']] += 1
                rounds += result_dict['rounds']
            if config['bbcode']['output']:
                if wins[1] > wins[2]:
                    output_file_bbcode.write('[td]' + attacker['name'] + ': ' + str(wins[1]) + '/' + str(wins[2]) +
                                             '/' + str(wins[0]) + '(' +
                                             str(round(float(rounds) / float(int(config['battle_runs'])), 1)) +
                                             ')[/td]')
                else:
                    output_file_bbcode.write('[td]' + defender['name'] + ': ' + str(wins[2]) + '/' + str(wins[1]) +
                                             '/' + str(wins[0]) + '(' +
                                             str(round(float(rounds) / float(int(config['battle_runs'])), 1)) +
                                             ')[/td]')
            logging.critical('====================')
            logging.critical(attacker['name'] + ': ' + str(wins[1]))
            logging.critical(defender['name'] + ': ' + str(wins[2]))
            logging.critical('Ties: ' + str(wins[0]))
            logging.critical('Average battle length: ' +
                             str(round(float(rounds) / float(int(config['battle_runs'])), 1)))
            if config['csv']['output']:
                if wins[1] > wins[2]:
                    output_text = attacker['name'] + ':' + str(wins[1]) + '/' + str(wins[2]) + '/' + \
                                  str(wins[0]) + '(' + str(round(float(rounds) / float(config['battle_runs']), 1)) + ')'
                else:
                    output_text = defender['name'] + ':' + str(wins[2]) + '/' + str(wins[1]) + '/' + \
                                  str(wins[0]) + '(' + str(round(float(rounds) / float(config['battle_runs']), 1)) + ')'
                csv_line[defender['name']] = output_text
        completed_attackers.append(attacker['name'])
        if config['bbcode']['output']:
            output_file_bbcode.write('[/tr]')
        if config['csv']['output']:
            csv_writer.writerow(csv_line)
    if config['bbcode']['output']:
        output_file_bbcode.write('[/table]')
        output_file_bbcode.close()
    if config['csv']['output']:
        output_file_csv.close()


def list_vs_list(attacker_list, defender_list):
    if config['csv']['output']:
        try:
            output_file_csv = open(config['csv']['path'], 'wb')
        except BaseException as why:
            logging.error('Failed to open CSV file ' + config['csv']['path'] + ' - ' + str(why))
            config['csv']['output'] = False
    if config['bbcode']['output']:
        try:
            output_file_bbcode = open(config['bbcode']['path'], 'wb')
        except BaseException as why:
            logging.error('Failed to open BBCode file ' + config['bbcode']['path'] + ' - ' + str(why))
            config['bbcode']['output'] = False
    if config['bbcode']['output']:
        output_file_bbcode.write('[table][tr][td]Attacker \ Defender[/td]')
    if config['csv']['output']:
        csv_fields = ['Attacker']
    for defender in defender_list:
        if config['bbcode']['output']:
            output_file_bbcode.write('[td][b]' + defender['name'] + ' (Skill ' + str(defender['skill']) + ')[/b][/td]')
        if config['csv']['output']:
            csv_fields.append(defender['name'])
    if config['bbcode']['output']:
        output_file_bbcode.write('[/tr]')
    if config['csv']['output']:
        csv_writer = csv.DictWriter(output_file_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL,
                                    fieldnames=csv_fields)
        csv_writer.writeheader()
    for attacker in attacker_list:
        if config['bbcode']['output']:
            output_file_bbcode.write('[tr][td][b]' + attacker['name'] + ' (Skill ' + str(attacker['skill']) + ')[/b][/td]')
        if config['csv']['output']:
            csv_line = {'Attacker': attacker['name']}
        for defender in defender_list:
            wins = [0, 0, 0]  # Ties, Attacker, Defender
            rounds = 0
            for battle in range(0, int(config['battle_runs'])):
                attacking_unit = unit_create_from_dict(attacker)
                defending_unit = unit_create_from_dict(defender)
                result_dict = one_vs_one(attacking_unit, defending_unit)
                wins[result_dict['winner']] += 1
                rounds += result_dict['rounds']
            if config['bbcode']['output']:
                output_file_bbcode.write('[td]' + str(wins[1]) + '/' + str(wins[2]) +
                                         '/' + str(wins[0]) + '/' +
                                         str(round(float(rounds) / float(int(config['battle_runs'])), 1)) +
                                         '[/td]')
            logging.critical('====================')
            logging.critical(attacker['name'] + ': ' + str(wins[1]))
            logging.critical(defender['name'] + ': ' + str(wins[2]))
            logging.critical('Ties: ' + str(wins[0]))
            logging.critical('Average battle length: ' +
                             str(round(float(rounds) / float(int(config['battle_runs'])), 1)))
            if config['csv']['output']:
                output_text = str(wins[1]) + '/' + str(wins[2]) + '/' + \
                              str(wins[0]) + '/' + str(round(float(rounds) / float(config['battle_runs']), 1))
                csv_line[defender['name']] = output_text
        if config['bbcode']['output']:
            output_file_bbcode.write('[/tr]')
        if config['csv']['output']:
            csv_writer.writerow(csv_line)
    if config['bbcode']['output']:
        output_file_bbcode.write('[/table]')
        output_file_bbcode.close()
    if config['csv']['output']:
        output_file_csv.close()


def combatant_stat_string(combatant):
    stat_string = combatant['name'] + ': '
    stat_list = ['Skill', 'Points', 'Type', 'Armor', 'Structure', 'Weapons', 'Move', 'Jump', 'Special']
    for stat_item in stat_list:
        if stat_item.lower() in combatant:
            stat_string += stat_item + ': ' + str(combatant[stat_item.lower()]) + ', '
    stat_string = stat_string.rstrip(', ')
    return stat_string


def single_fight(attacker, defender):
    logging.critical(combatant_stat_string(attacker))
    logging.critical(combatant_stat_string(defender))
    wins = [0, 0, 0]  # Ties, Attacker, Defender
    rounds = 0
    for battle in range(0, int(config['battle_runs'])):
        attacking_unit = unit_create_from_dict(attacker)
        defending_unit = unit_create_from_dict(defender)
        result_dict = one_vs_one(attacking_unit, defending_unit)
        wins[result_dict['winner']] += 1
        rounds += result_dict['rounds']
    logging.critical('====================')
    logging.critical(attacker['name'] + ': ' + str(wins[1]))
    logging.critical(defender['name'] + ': ' + str(wins[2]))
    logging.critical('Ties: ' + str(wins[0]))
    logging.critical('Average battle length: ' +
                     str(round(float(rounds) / float(int(config['battle_runs'])), 1)))


def unit_from_list_by_name(name, unit_list):
    for unit in unit_list:
        if name == unit['name']:
            return unit
    raise RuntimeError('Unit "' + name + '" not found in unit list.')


def main():
    config_set_from_command_line()
    logging_configure(config['log_file'], int(config['log_level']))
    random.seed()
    unit_list = unit_list_read_from_json(config['unit_list_path'])
    if config['attacker'] is not None and config['defender'] is not None:
        attacker = unit_from_list_by_name(config['attacker'], unit_list)
        defender = unit_from_list_by_name(config['defender'], unit_list)
        single_fight(attacker, defender)
    elif len(config['attacker_list']) > 0 and len(config['defender_list']) > 0:
        attacker_list = []
        defender_list = []
        for attacker in config['attacker_list']:
            attacker_list.append(unit_from_list_by_name(attacker, unit_list))
        for defender in config['defender_list']:
            defender_list.append(unit_from_list_by_name(defender, unit_list))
        list_vs_list(attacker_list, defender_list)
    else:
        unit_list_fight(unit_list)


if __name__ == "__main__":
    main()
