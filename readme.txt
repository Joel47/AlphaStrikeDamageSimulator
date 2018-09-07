Supported Specials:
RFA, SHLD, AMS, RAMS, ARM, CR, CASE, CASEII, BHJ2, BHJ3, RHS, STL, ENE, LG, VLG, SLG

Used for other specials: LRM, SRM, IF

Usage instructions:
damage_simulator.py --config=config.json [--other_options]

(Note: you may have to prepend the path to your Python executable to the command line above if it's not in your path.)

If config.json is alongside the script you don't need to include that option.
For a full list of command line options run with -h
Essentially, anything in the top level of the config.json file can be set; remember to wrap the value with quotes if it
contains spaces.

If attacker and defender are given, a single 1-v-1 battle will be run. CSV & BBCode output are disabled.
If attacker_list and defender_list are given (in the config file only), each attacker will be paired with each defender in grid form.
If only unit_list_path is given, each unit in the list will fight every other unit in the list.