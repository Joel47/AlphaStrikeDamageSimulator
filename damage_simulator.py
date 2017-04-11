import logging
import os
import shutil
import random

LOG_LEVEL = 30  # 10 = Debug, 20 = lots of info, 30 = just results
LOG_FILE = ''  # Set to '' to output to console; otherwise, path to log file
BATTLE_RUNS = 1000  # Number of battles per pairing to simulate
OUTPUT_AS_BBCODE = True  # if True, requires LOG_LEVEL = 30

SKILL_LEVEL = 4  # All units will be this skill unless directly set

# Constants for use below
MAX_ROUNDS = 100  # Avoid runaways

SHORT_RANGE = 0
MEDIUM_RANGE = 1
LONG_RANGE = 2
RANDOM_RANGE = -1

MECH = 0
VEHICLE = 1
PROTOMECH = 2
INFANTRY = 3
BATTLEARMOR = 4

TRACKED = 0
NAVAL = 1
WHEELED = 2
HOVER = 3
VTOL = 4
WIGE = 5

# Units to compute
# TODO - replace with import
UNIT_LIST = []
# Originals
# UNIT_LIST.append({'name':'Uziel UZL-3S', 'type':MECH, 'armor':4, 'structure':2, 'weapons':[3, 3, 0], 'move':12})
# UNIT_LIST.append({'name':'Lynx LNX-8Q', 'type':MECH, 'armor':6, 'structure':5, 'weapons':[2, 2, 0], 'move':10, 'special':['ENE']})
# UNIT_LIST.append({'name':'Locust IIC 7', 'type':MECH, 'armor':3, 'structure':2, 'weapons':[3, 3, 0], 'move':16, 'special':['CASE']})
# UNIT_LIST.append({'name':'Initiate INI-02', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[4, 4, 1], 'move':8, 'special':['CASE', 'AMS']})
# UNIT_LIST.append({'name':'Thunder Fox TDF-F11', 'type':MECH, 'armor':7, 'structure':2, 'weapons':[2, 2, 2], 'move':10, 'special':['ENE', 'CR']})
# UNIT_LIST.append({'name':'Catapult CPLT-C1', 'type':MECH, 'armor':5, 'structure':5, 'weapons':[2, 3, 2], 'move':8})
# UNIT_LIST.append({'name':'Crusader CRD-3R', 'type':MECH, 'armor':6, 'structure':5, 'weapons':[2, 2, 2], 'move':8})
# UNIT_LIST.append({'name':'Warhammer WHM-6R', 'type':MECH, 'armor':5, 'structure':6, 'weapons':[3, 3, 2], 'move':8})
# UNIT_LIST.append({'name':'Fire Falcon H', 'type':MECH, 'armor':3, 'structure':1, 'weapons':[5, 4, 0], 'move':16, 'special':['ENE']})
# UNIT_LIST.append({'name':'Gunsmith CH11-NG', 'type':MECH, 'armor':3, 'structure':1, 'weapons':[3, 3, 0], 'move':26, 'special':['ENE', 'RFA']})
# UNIT_LIST.append({'name':'Anubis ABS-5Z', 'type':MECH, 'armor':3, 'structure':1, 'weapons':[3, 3, 0], 'move':14, 'special':['ECM', 'TAG', 'STL']})

# Second run
UNIT_LIST.append({'name':'Uziel UZL-3S', 'type':MECH, 'armor':4, 'structure':2, 'weapons':[3, 3, 0], 'move':12})
UNIT_LIST.append({'name':'Lynx LNX-8Q', 'type':MECH, 'armor':6, 'structure':5, 'weapons':[2, 2, 0], 'move':10, 'special':['ENE']})
UNIT_LIST.append({'name':'Black Hawk (Nova) B', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[3, 3, 2], 'move':10, 'skill':4, 'motive':0, 'special':['CASE']})
UNIT_LIST.append({'name':'Black Hawk-KU BHKU-OB', 'type':MECH, 'armor':7, 'structure':3, 'weapons':[2, 2, 1], 'move':10, 'skill':4, 'motive':0})
UNIT_LIST.append({'name':'Cataphract CTF-3D', 'type':MECH, 'armor':6, 'structure':3, 'weapons':[3, 3, 2], 'move':8, 'skill':4, 'motive':0, 'special':['CASE']})
UNIT_LIST.append({'name':'Catapult CPLT-H2', 'type':MECH, 'armor':6, 'structure':5, 'weapons':[3, 3, 1], 'move':8, 'skill':4, 'motive':0})
UNIT_LIST.append({'name':'Cicada CDA-3F', 'type':MECH, 'armor':4, 'structure':2, 'weapons':[2, 2, 1], 'move':16, 'skill':4, 'motive':0, 'special':['ENE']})
UNIT_LIST.append({'name':'Victor VTR-9A1', 'type':MECH, 'armor':5, 'structure':6, 'weapons':[4, 4, 0], 'move':8, 'skill':4, 'motive':0})
UNIT_LIST.append({'name':'Watchman WTC-4DM', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[3, 3, 1], 'move':10, 'skill':4, 'motive':0, 'special':['ENE']})
UNIT_LIST.append({'name':'Wight WGT-2LAW', 'type':MECH, 'armor':3, 'structure':4, 'weapons':[2, 2, 1], 'move':8, 'skill':4, 'motive':0, 'special':['ENE']})  # Move should be 14, but special rules
UNIT_LIST.append({'name':'Wulfen C', 'type':MECH, 'armor':3, 'structure':1, 'weapons':[2, 2, 0], 'move':20, 'skill':4, 'motive':0, 'special':['ENE', 'STL']})

#  UNIT_LIST.append(['Wasp WSP-3A', MECH, 2, 1, [1, 1, 0], 10, 4, 0, ['ENE']])
#  UNIT_LIST.append(['Dasher E', MECH, 1, 1, [2, 1, 1], 26, 4, 0, ['CASE']])

# Self-test
# UNIT_LIST.append({'name':'A', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[3, 3, 2], 'move':10, 'skill':4, 'motive':0, 'special':['CASE']})
# UNIT_LIST.append({'name':'B', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[3, 3, 2], 'move':10, 'skill':4, 'motive':0, 'special':['CASE']})
# UNIT_LIST.append({'name':'C', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[3, 3, 2], 'move':10, 'skill':4, 'motive':0, 'special':['CASE']})
# UNIT_LIST.append({'name':'D', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[3, 3, 2], 'move':10, 'skill':4, 'motive':0, 'special':['CASE']})
# UNIT_LIST.append({'name':'E', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[3, 3, 2], 'move':10, 'skill':4, 'motive':0, 'special':['CASE']})
# UNIT_LIST.append({'name':'F', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[3, 3, 2], 'move':10, 'skill':4, 'motive':0, 'special':['CASE']})
# UNIT_LIST.append({'name':'G', 'type':MECH, 'armor':5, 'structure':3, 'weapons':[3, 3, 2], 'move':10, 'skill':4, 'motive':0, 'special':['CASE']})


class CombatUnit(object):

    def __init__(self, name, type, armor, structure, weapons, movement, skill, motive_type=0, special=None):
        self.name = name
        self.type = type
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
                self.movement = min(0, self.movement - 2)
            elif motive_roll == 11:
                movement_loss = divide_by_two_round_up(self.movement)
                self.movement -= movement_loss
            elif motive_roll == 12:
                self.movement = 0
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
                movement_loss = min(2, divide_by_two_round_up(self.movement))
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
                # TODO - figure out a way to implement this
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


def unit_create_from_dict(stat_dict):
    #name, type, armor, structure, weapons, movement, skill, motive_type=0, special=None
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
        unit_skill = SKILL_LEVEL
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
        except BaseException as why:
            raise IOError('Unable to create log folder: ' + str(why))
        # Check for existing log file and rename if it exists
        if os.path.isfile(output_log_file_directory + output_log_file_name):
            file_increment = 1
            while os.path.isfile(output_log_file_directory + output_log_file_name + '_' + str(file_increment)):
                file_increment += 1
            try:
                shutil.move(output_log_file_directory + output_log_file_name, output_log_file_directory +
                            output_log_file_name + '_' + str(file_increment))
            except BaseException as why:
                raise RuntimeError('Unable to copy old output log.  Stopping so as not to overwrite data. '
                                   + str(why))
        logging.basicConfig(filename=output_log_file_directory + output_log_file_name, level=log_level,
                            format=log_format)
    else:
        logging.basicConfig(level=log_level, format=log_format)


def two_d6():
    die1 = random.randint(1,6)
    die2 = random.randint(1,6)
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


def one_vs_one(attacker, defender, range_band):
    round_count = 0
    attacker_roll_total = 0
    attacker_rolls = 0
    defender_roll_total = 0
    defender_rolls = 0
    while attacker.structure > 0 and defender.structure > 0:
        round_count += 1
        logging.debug('========== ROUND ' + str(round_count) + ' ==========')
        if range_band not in [SHORT_RANGE, MEDIUM_RANGE, LONG_RANGE]:
            # Start at Long, then random short & medium
            if round_count == 1:
                current_range_band = LONG_RANGE
                range_mod = 4
                logging.debug('First round: long range')
            else:
                current_range_band = random.randint(0,1)
                range_mod = 2 * current_range_band
                logging.debug('Later round; range mod ' + str(range_mod))
        else:
            # Fixed range
            range_mod = 2 * range_band
            current_range_band = range_band
        if attacker.movement_mod == 0:
            attacker_mods = -1
        else:
            attacker_mods = 0
        if defender.movement_mod == 0:
            defender_mods = -1
        else:
            defender_mods = 0
        if 'STL' in attacker.special:
            defender_mods += int(float(range_mod) / 2)
        if 'STL' in defender.special:
            attacker_mods += int(float(range_mod) / 2)
        logging.debug(attacker.name + ' shoots ' + defender.name)
        defender_was_hit, actual_roll = roll_to_hit(attacker.skill + attacker_mods, range_mod, defender.movement_mod)
        attacker_roll_total += actual_roll
        attacker_rolls += 1
        logging.debug(defender.name + ' shoots ' + attacker.name)
        attacker_was_hit, actual_roll = roll_to_hit(defender.skill + defender_mods, range_mod, attacker.movement_mod)
        defender_roll_total += actual_roll
        defender_rolls += 1
        attacker_weapons = int(attacker.weapons[current_range_band])
        defender_weapons = int(defender.weapons[current_range_band])
        if attacker_was_hit:
            attacker.motive_check()
            attacker.apply_damage(defender_weapons, defender.special)
        if defender_was_hit:
            defender.motive_check()
            defender.apply_damage(attacker_weapons, attacker.special)
        attacker.state_log()
        defender.state_log()
        if round_count > MAX_ROUNDS:
            logging.info('Maximum rounds exceeded; calling the battle.')
            break
    if attacker.structure > 0 and defender.structure > 0:
        logging.info('Draw.')
        logging.info('Both units survived.')
        winner = 0
    elif attacker.structure <= 0 and defender.structure <= 0:
        logging.info('Draw.')
        winner = 0
    elif defender.structure > 0:
        logging.info('Winner: ' + defender.name)
        winner = 2
    elif attacker.structure > 0:
        logging.info('Winner: ' + attacker.name)
        winner = 1
    else:
        logging.error('Unsupported game end state.')
        winner = 0
    return {'winner': winner, 'rounds': round_count,
            'attacker_roll_total': attacker_roll_total, 'attacker_rolls': attacker_rolls,
            'defender_roll_total': defender_roll_total, 'defender_rolls': defender_rolls}

if __name__ == "__main__":
    logging_configure(LOG_FILE, LOG_LEVEL)
    random.seed()
    # dice_test(100000)
    attacker_roll_total = 0
    attacker_rolls = 0
    defender_roll_total = 0
    defender_rolls = 0
    defender_list = []
    completed_attackers = []
    if OUTPUT_AS_BBCODE:
        logging.critical('[table][tr][td]Attacker \ Defender[/td]')
    for defender in UNIT_LIST:
        defender_list.append(defender)
        if OUTPUT_AS_BBCODE:
            logging.critical('[td]' + defender['name'] + '[/td]')
    if OUTPUT_AS_BBCODE:
        logging.critical('[/tr]')
    for attacker in UNIT_LIST:
        if OUTPUT_AS_BBCODE:
            logging.critical('[tr][td]' + attacker['name'] + '[/td]')
        for defender in defender_list:
            if attacker['name'] == defender['name']:
                logging.debug('Identical units; skipping.')
                if OUTPUT_AS_BBCODE:
                    logging.critical('[td]-----[/td]')
                continue
            if attacker['name'] in completed_attackers:
                # TODO - this isn't working
                logging.debug('Pairing already run; skipping.')
                if OUTPUT_AS_BBCODE:
                    logging.critical('[td]-----[/td]')
                continue
            wins = [0,0,0]  # Ties, Attacker, Defender
            rounds = 0
            for battle in range(0, BATTLE_RUNS):
                attacking_unit = unit_create_from_dict(attacker)
                defending_unit = unit_create_from_dict(defender)
                result_dict = one_vs_one(attacking_unit, defending_unit, RANDOM_RANGE)
                wins[result_dict['winner']] += 1
                rounds += result_dict['rounds']
                attacker_roll_total += result_dict['attacker_roll_total']
                attacker_rolls += result_dict['attacker_rolls']
                defender_roll_total += result_dict['defender_roll_total']
                defender_rolls += result_dict['defender_rolls']
            if OUTPUT_AS_BBCODE:
                if wins[1] > wins[2]:
                    logging.critical('[td]' + attacker['name'] + ': ' + str(wins[1]) + '/' + str(wins[2]) + '/' +
                                     str(wins[0]) + '(' + str(int(round(float(rounds) / float(BATTLE_RUNS), 0))) +
                                     ')[/td]')
                elif wins[2] > wins[1]:
                    logging.critical('[td]' + defender['name'] + ': ' + str(wins[2]) + '/' + str(wins[1]) + '/' +
                                     str(wins[0]) + '(' + str(int(round(float(rounds) / float(BATTLE_RUNS), 0))) +
                                     ')[/td]')
            else:
                logging.critical('====================')
                logging.critical(attacker['name'] + ': ' + str(wins[1]))
                logging.critical(defender['name'] + ': ' + str(wins[2]))
                logging.critical('Ties: ' + str(wins[0]))
                logging.critical('Average battle length: ' + str(int(round(float(rounds) / float(BATTLE_RUNS), 0))))
        completed_attackers.append(attacker['name'])
        if OUTPUT_AS_BBCODE:
            logging.critical('[/tr]')
    if OUTPUT_AS_BBCODE:
        logging.critical('[/table]')
    logging.debug('Average attacker to-hit roll: ' + str(round(attacker_roll_total/float(attacker_rolls), 3)))
    logging.debug('Average defender to-hit roll: ' + str(round(defender_roll_total / float(defender_rolls), 3)))
