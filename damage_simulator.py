import logging
import os
import shutil
import random

# To set variables, scroll down to the bottom

# Constants for use below
SHORT_RANGE = 0
MEDIUM_RANGE = 1
LONG_RANGE = 2

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

    def apply_damage(self, damage):
        logging.debug('Applying ' + str(damage) + ' damage to ' + self.name)
        if damage <= self.armor:
            self.armor -= damage
            logging.debug(str(damage) + ' applied to armor; ' + str(self.armor) + ' armor remaining.')
        else:
            if self.armor > 0:
                logging.debug('Armor destroyed.')
            damage -= self.armor
            self.armor = 0
            if damage <= self.structure:
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
    return int(10 * ((x + 5) // 20))


def logging_configure(log_path='', log_level=10):
    if len(log_path) > 0:
        log_to_file = True
        output_log_file_directory = os.path.dirname(log_path) + '/'
        output_log_file_name = os.path.splitext(os.path.basename(log_path))[0]
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
        if os.path.isfile(output_log_file_directory + output_log_file_name + '.log'):
            file_increment = 1
            while os.path.isfile(output_log_file_directory + output_log_file_name + '_' + str(file_increment) + '.log'):
                file_increment += 1
            try:
                shutil.move(output_log_file_directory + output_log_file_name + '.log', output_log_file_directory +
                            output_log_file_name + '_' + str(file_increment) + '.log')
            except BaseException as why:
                raise RuntimeError('Unable to copy old output log.  Stopping so as not to overwrite data. '
                                   + str(why))
        logging.basicConfig(filename=output_log_file_directory + output_log_file_name + '.log', level=log_level,
                            format=log_format)
    else:
        logging.basicConfig(level=log_level, format=log_format)


def two_d6():
    die1 = random.randint(1,6)
    die2 = random.randint(1,6)
    return die1 + die2


def roll_to_hit(skill, range_mod, def_mod, terrain=0):
    target_number = skill + range_mod + def_mod + terrain
    die_roll = two_d6()
    if die_roll >= target_number:
        logging.debug('Hit! (Needed ' + str(target_number) + ', rolled ' + str(die_roll) + ')')
        return True
    else:
        logging.debug('Miss! (Needed ' + str(target_number) + ', rolled ' + str(die_roll) + ')')
        return False


def one_vs_one(attacker, defender, range_band):
    round_count = 1
    while attacker.structure > 0 and defender.structure > 0:
        logging.info('========== ROUND ' + str(round_count) + ' ==========')
        # TODO - if movement_mod == 0, decrease skill by 1 to simulate standing still
        logging.debug(attacker.name + ' attacks ' + defender.name)
        defender_was_hit = roll_to_hit(attacker.skill, range_band * 2, defender.movement_mod)
        logging.debug(defender.name + ' attacks ' + attacker.name)
        attacker_was_hit = roll_to_hit(defender.skill, range_band * 2, attacker.movement_mod)
        if attacker_was_hit:
            attacker.motive_check()
            attacker.apply_damage(defender.weapons[range_band])
        if defender_was_hit:
            defender.motive_check()
            defender.apply_damage(attacker.weapons[range_band])
        round_count += 1
    if attacker.structure > defender.structure:
        logging.info('Winner: ' + attacker.name)
        return 1
    elif defender.structure > attacker.structure:
        logging.info('Winner: ' + defender.name)
        return 2
    else:
        logging.info('Draw.')
        return 0


if __name__ == "__main__":
    # Set the second field to 10 to see everything, 20 to see some, and 30 to just see results
    logging_configure('', 30)
    random.seed()
    wins = [0,0,0]
    for battle in range(0,1000):
        # Set attacker and defender stats here
        # Format: 'Name', type (see constants at top), armor, structure, damage array, movement in inches, skill
        attacker = CombatUnit('CPLT-C1', MECH, 5, 5, [2, 3, 2], 8, 4)
        defender = CombatUnit('CPLT-A1', MECH, 6, 5, [1, 2, 2], 8, 4)
        winner = one_vs_one(attacker, defender, LONG_RANGE)
        wins[winner] += 1
    logging.info('====================')
    logging.critical('Attacker: ' + str(wins[1]))
    logging.critical('Defender: ' + str(wins[2]))
    logging.critical('Ties: ' + str(wins[0]))