import logging
import os
import shutil
import random
import csv
import json
import ConfigParser

CONFIG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'damage_simulator.cfg')

# Constants for use below
MAX_ROUNDS = 100  # Avoid runaways

SHORT_RANGE = 0
MEDIUM_RANGE = 1
LONG_RANGE = 2
RANDOM_RANGE = -1
FAST_UNIT_CAUSES_SLOW_APPROACH = -2
INITIATIVE_HELPS_FASTER_MINIMIZE_HIT_CHANCE = -3
INITIATIVE_HELPS_FASTER_MAXIMIZE_DAMAGE = -4

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


def config_read(config_file):
    my_config = ConfigParser.SafeConfigParser({'log_file_path': '',
                                               'csv_output_file_path': '',
                                               'bbcode_output_file_path': '',
                                               'log_level': 30,
                                               'battle_runs': 1,
                                               'range_determination': 'fixed_short'})
    my_config.read(config_file)
    dict1 = {}
    section = 'run_settings'
    options = my_config.options(section)
    for option in options:
        try:
            dict1[option] = my_config.get(section, option)
            if dict1[option] == -1:
                print("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1


class CombatUnit(object):

    def __init__(self, name, unit_type, armor, structure, weapons, movement, skill, motive_type=0, special=None):
        self.name = name
        self.type = unit_type
        self.armor = armor
        self.structure = structure
        self.weapons = weapons
        self.movement = movement
        self.movement_mod = movement_mod(self.movement)
        self.motive_type = motive_type
        self.skill = skill
        if not (special is None):
            self.special = special
        else:
            self.special = []
        self.crits = []

    def apply_damage(self, damage, attacker_specials=''):
        logging.debug('Applying ' + str(damage) + ' damage to ' + self.name)
        if 'RFA' in self.special:
            if 'ENE' in attacker_specials:
                logging.debug('Reflective Armor reduces damage by half.')
                damage = divide_by_two_round_up(damage)
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
            self.movement_mod = movement_mod(self.movement)

    def apply_crit(self, crit_roll):
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
                    self.apply_damage(1)
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
                    # decrease firepower to 50% to simulate overheating
                    for range_band in [0, 1, 2]:
                        self.weapons[range_band] = divide_by_two_round_up(self.weapons[range_band])
                    logging.debug('Weapons now ' + str(self.weapons))
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
                self.movement_mod = movement_mod(self.movement)
                logging.debug('New movement mod: ' + str(self.movement_mod))
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
                    self.apply_damage(1)
                else:
                    logging.debug('Unit destroyed.')
                    self.structure = 0
            elif crit_roll == 3:
                logging.debug('Crew Stunned')
                self.crits.append('Crew Stunned')
                # TODO - figure out a way to implement this; probably add to self.crits and remove it when triggered.
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
                    self.movement_mod = movement_mod(self.movement)
                    logging.debug('New movement mod: ' + str(self.movement_mod))
                    for range_band in [0, 1, 2]:
                        self.weapons[range_band] = divide_by_two_round_up(self.weapons[range_band])
            else:
                logging.debug('No crit.')
        elif self.type == PROTOMECH:
            logging.debug('Crits not yet implemented for Protomechs')
            # TODO - implement crits

    def state_log(self):
        logging.debug(self.name + ': ' + str(self.armor) + '/' + str(self.structure) + ' ' +
                      str(self.weapons) + ' ' + str(self.crits))


def unit_create_from_dict(stat_dict, default_skill_level=4):
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
        unit_weapons = [0, 0, 0]
    try:
        unit_move = stat_dict['move']
    except KeyError:
        unit_move = 0
    try:
        unit_skill = stat_dict['skill']
    except KeyError:
        unit_skill = default_skill_level
    try:
        unit_motive = stat_dict['motive']
    except KeyError:
        unit_motive = 0
    try:
        unit_special = stat_dict['special']
    except KeyError:
        unit_special = []
    return CombatUnit(unit_name, unit_type, unit_armor, unit_structure, unit_weapons, unit_move, unit_skill,
                      unit_motive, unit_special)


def unit_list_read_from_json(json_path):
    with open(json_path) as json_data:
        units = json.load(json_data)
    logging.debug('Read unit list ' + json_path + ':')
    logging.debug(str(units))
    return units


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
        return True, die_roll
    else:
        logging.debug('Miss! (Needed ' + str(target_number) + ', rolled ' + str(die_roll) + ')')
        return False, die_roll


def range_get(range_algorithm, current_round, initiative_winner, range_previous, attacker, defender):
    if attacker.movement == 0 and defender.movement == 0:
        return range_previous
    if range_algorithm == SHORT_RANGE:
        return SHORT_RANGE
    elif range_algorithm == MEDIUM_RANGE:
        return MEDIUM_RANGE
    elif range_algorithm == LONG_RANGE:
        return MEDIUM_RANGE
    elif range_algorithm == RANDOM_RANGE:
        if current_round == 1:
            logging.debug('Randomly determined range: First round; long range.')
            return LONG_RANGE
        elif current_round == 2:
            logging.debug('Randomly determined range: Second round; medium range.')
            return MEDIUM_RANGE
        else:
            # Randomly choose between short and medium range
            new_range = random.randint(0, 1)
            logging.debug('Randomly determined range: ' + str(new_range))
            return new_range
    elif range_algorithm == FAST_UNIT_CAUSES_SLOW_APPROACH:
        if attacker.movement > defender.movement:
            faster_unit = attacker
            slower_unit = defender
        else:
            faster_unit = defender
            slower_unit = attacker
        speed_difference = abs(attacker.movement - defender.movement)
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

def one_vs_one(first_unit, second_unit, range_algorithm):
    round_count = 0
    battle_attacker_roll_total = 0
    battle_attacker_rolls = 0
    battle_defender_roll_total = 0
    battle_defender_rolls = 0
    range_previous = LONG_RANGE
    while first_unit.structure > 0 and second_unit.structure > 0:
        round_count += 1
        logging.debug('========== ROUND ' + str(round_count) + ' ==========')
        initiative_winner = random.randint(0,1)
        range_band = range_get(range_algorithm, round_count, initiative_winner, range_previous, first_unit, second_unit)
        range_mod = 2 * range_band
        range_previous = range_band
        if first_unit.movement_mod == 0:
            attacker_mods = -1
        else:
            attacker_mods = 0
        if second_unit.movement_mod == 0:
            defender_mods = -1
        else:
            defender_mods = 0
        if 'STL' in first_unit.special:
            defender_mods += int(float(range_mod) / 2)
        if 'STL' in second_unit.special:
            attacker_mods += int(float(range_mod) / 2)
        logging.debug(first_unit.name + ' shoots ' + second_unit.name)
        defender_was_hit, actual_roll = roll_to_hit(first_unit.skill + attacker_mods, range_mod,
                                                    second_unit.movement_mod)
        battle_attacker_roll_total += actual_roll
        battle_attacker_rolls += 1
        logging.debug(second_unit.name + ' shoots ' + first_unit.name)
        attacker_was_hit, actual_roll = roll_to_hit(second_unit.skill + defender_mods, range_mod,
                                                    first_unit.movement_mod)
        battle_defender_roll_total += actual_roll
        battle_defender_rolls += 1
        attacker_weapons = int(first_unit.weapons[range_band])
        defender_weapons = int(second_unit.weapons[range_band])
        if attacker_was_hit:
            first_unit.motive_check()
            first_unit.apply_damage(defender_weapons, second_unit.special)
        if defender_was_hit:
            second_unit.motive_check()
            second_unit.apply_damage(attacker_weapons, first_unit.special)
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
    return {'winner': winner, 'rounds': round_count,
            'attacker_roll_total': battle_attacker_roll_total, 'attacker_rolls': battle_attacker_rolls,
            'defender_roll_total': battle_defender_roll_total, 'defender_rolls': battle_defender_rolls}


if __name__ == "__main__":
    try:
        config = config_read(CONFIG_FILE)
    except BaseException as why:
        print('Failed to read config file: ' + CONFIG_FILE)
        print('Error: ' + str(why))
        quit()
    logging_configure(config['log_file_path'], int(config['log_level']))
    unit_list = unit_list_read_from_json(config['unit_list_path'])
    random.seed()
    # dice_test(100000)
    attacker_roll_total = 0
    attacker_rolls = 0
    defender_roll_total = 0
    defender_rolls = 0
    if config['range_determination'] == 'fixed_short':
        range_determination_method = SHORT_RANGE
    elif config['range_determination'] == 'fixed_medium':
        range_determination_method = MEDIUM_RANGE
    elif config['range_determination'] == 'fixed_long':
        range_determination_method = LONG_RANGE
    elif config['range_determination'] == 'random':
        range_determination_method = RANDOM_RANGE
    elif config['range_determination'] == 'fast_unit_causes_slow_approach':
        range_determination_method = FAST_UNIT_CAUSES_SLOW_APPROACH
    # TODO - range_determination = initiative_helps_faster_minimize_hit_chance  ***NOT YET IMPLEMENTED***
    # TODO - range_determination = initiative_helps_faster_maximize_damage  ***NOT YET IMPLEMENTED***

    if len(config['csv_output_file_path']) > 0:
        csv_write = True
        bbcode_write = False
        try:
            output_file_csv = open(config['csv_output_file_path'], 'wb')
        except BaseException as why:
            logging.error('Failed to open CSV file ' + config['csv_output_file_path'] + ' - ' + str(why))
            csv_write = False
    else:
        csv_write = False
    if len(config['bbcode_output_file_path']) > 0:
        bbcode_write = True
        try:
            output_file_bbcode = open(config['bbcode_output_file_path'], 'wb')
        except BaseException as why:
            logging.error('Failed to open BBCode file ' + config['bbcode_output_file_path'] + ' - ' + str(why))
            bbcode_write = False
    else:
        bbcode_write = False
    defender_list = []
    completed_attackers = []
    if bbcode_write:
        output_file_bbcode.write('[table][tr][td]Attacker \ Defender[/td]')
    if csv_write:
        csv_fields = ['Attacker']
    for defender in unit_list:
        defender_list.append(defender)
        if bbcode_write:
            output_file_bbcode.write('[td]' + defender['name'] + '[/td]')
        if csv_write:
            csv_fields.append(defender['name'])
    if bbcode_write:
        output_file_bbcode.write('[/tr]')
    if csv_write:
        csv_writer = csv.DictWriter(output_file_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL,
                                    fieldnames=csv_fields)
        csv_writer.writeheader()
    for attacker in unit_list:
        if bbcode_write:
            output_file_bbcode.write('[tr][td]' + attacker['name'] + '[/td]')
        if csv_write:
            csv_line = {'Attacker': attacker['name']}
        for defender in defender_list:
            if attacker['name'] == defender['name']:
                logging.debug('Identical units; skipping.')
                if bbcode_write:
                    output_file_bbcode.write('[td]-----[/td]')
                if csv_write:
                    csv_line[defender['name']] = 'N/A'
                continue
            if attacker['name'] in completed_attackers:
                # TODO - this isn't working
                logging.debug('Pairing already run; skipping.')
                if bbcode_write:
                    output_file_bbcode.write('[td]-----[/td]')
                if csv_write:
                    csv_line[defender['name']] = 'N/A'
                continue
            wins = [0, 0, 0]  # Ties, Attacker, Defender
            rounds = 0
            for battle in range(0, int(config['battle_runs'])):
                attacking_unit = unit_create_from_dict(attacker, int(config['skill_level_default']))
                defending_unit = unit_create_from_dict(defender, int(config['skill_level_default']))
                result_dict = one_vs_one(attacking_unit, defending_unit, range_determination_method)
                wins[result_dict['winner']] += 1
                rounds += result_dict['rounds']
                attacker_roll_total += result_dict['attacker_roll_total']
                attacker_rolls += result_dict['attacker_rolls']
                defender_roll_total += result_dict['defender_roll_total']
                defender_rolls += result_dict['defender_rolls']
            if bbcode_write:
                if wins[1] > wins[2]:
                    output_file_bbcode.write('[td]' + attacker['name'] + ': ' + str(wins[1]) + '/' + str(wins[2]) + '/' +
                                     str(wins[0]) + '(' + str(round(float(rounds) / float(int(config['battle_runs'])), 1)) +
                                     ')[/td]')
                else:
                    output_file_bbcode.write('[td]' + defender['name'] + ': ' + str(wins[2]) + '/' + str(wins[1]) + '/' +
                                     str(wins[0]) + '(' + str(round(float(rounds) / float(int(config['battle_runs'])), 1)) +
                                     ')[/td]')
            logging.critical('====================')
            logging.critical(attacker['name'] + ': ' + str(wins[1]))
            logging.critical(defender['name'] + ': ' + str(wins[2]))
            logging.critical('Ties: ' + str(wins[0]))
            logging.critical('Average battle length: ' + str(round(float(rounds) / float(int(config['battle_runs'])), 1)))
            if csv_write:
                if wins[1] > wins[2]:
                    output_text = attacker['name'] + ':' + str(wins[1]) + '/' + str(wins[2]) + '/' + \
                                  str(wins[0]) + '(' + str(round(float(rounds) / float(config['battle_runs']), 1)) + ')'
                else:
                    output_text = defender['name'] + ':' + str(wins[2]) + '/' + str(wins[1]) + '/' + \
                                  str(wins[0]) + '(' + str(round(float(rounds) / float(config['battle_runs']), 1)) + ')'
                csv_line[defender['name']] = output_text
        completed_attackers.append(attacker['name'])
        if bbcode_write:
            output_file_bbcode.write('[/tr]')
        if csv_write:
            csv_writer.writerow(csv_line)
    if bbcode_write:
        output_file_bbcode.write('[/table]')
        output_file_bbcode.close()
    if csv_write:
        output_file_csv.close()
    logging.debug('Average attacker to-hit roll: ' + str(round(attacker_roll_total/float(attacker_rolls), 3)))
    logging.debug('Average defender to-hit roll: ' + str(round(defender_roll_total / float(defender_rolls), 3)))
