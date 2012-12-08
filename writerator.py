#!/usr/bin/env python3

# Copyright 2012 Bill Tyros
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import logging
import sys
import time

import argparse
import configparser
import subprocess

import cProfile
import pstats

from texttools import Text


def main():   
    config = configparser.ConfigParser()
    config.read('settings.ini')
    
    parser = make_parser(config)
    
    args = parser.parse_args()
    
    set_logging_level(args.debug)
    
    logging.debug(str(args))
    
    (filename_in, filename_out) = get_filenames(args.file_in)
    
    text = Text(filename_in)
    
    output_lines = get_output(text, args, config)
    
    if args.output:
        output_to_file(filename_out, output_lines)
    else:
        output_to_console(output_lines)

def get_batch_args_list(config, batch_name):
    params_list = []
    for example_name in config[batch_name]:
        params_list.append(config[batch_name][example_name])
            
    return params_list


def make_parser(config):
    main_parser = argparse.ArgumentParser()
    
    
    main_parser.add_argument("file_in", help="filename of input file")
    
    main_parser.add_argument("-d", "--debug", 
                        help="displays logging debug messages.",
                        action="store_true")
    
    main_parser.add_argument("-o", "--output",
                        help="""writes output to a .txt file""",
                        action="store_true")
    
    type_parent_parser = argparse.ArgumentParser(add_help=False)
    
    type_parent_parser.add_argument("-t", "--type", choices=['w', 'c', 's'],
                                    default=config['parser']['TypeOfElement'], type=str,
                                    help="""determine the type of text elements 
                                    (words, characters, sentences) to analyze""" )
    
    show_parent_parser = argparse.ArgumentParser(add_help=False)
    
    show_parent_parser.add_argument("-s", "--show", metavar="N", type=int,
                                    default=int(config['parser']['NumberToShow']),
                                    help="""choose the number of results to 
                                    show (if applicable)""")
    
    
    subparsers = main_parser.add_subparsers(help="commands", dest="command")
    
    poem_parser = subparsers.add_parser("poem", help=
                                              """generate randomized poems""",
                                              parents=[show_parent_parser])
    
    poem_group = poem_parser.add_mutually_exclusive_group()
    
    poem_group.add_argument("-l", "--syllables", nargs='+', metavar="N",
                            type=int,
                            help="""generate a poem by specifying the number of 
                            syllables for each line in the poem.""")
    
    poem_group.add_argument("-p", "--preset", metavar="PRESET",
                            choices=['h', 's'],
                            help="""generate a poem by specifying a preset.""")
    
    poem_group.add_argument("-c", "--shortcut", metavar="N", type=int, nargs=2, 
                            help="""generate a poem by specifying the number of 
                            syllables per line and the number of lines.""")
    
    
    count_parser = subparsers.add_parser("count", help=
                                           """count occurrences of elements 
                                           within the text""",
                                           parents=[type_parent_parser, show_parent_parser])
    
    count_parser.add_argument("-o", "--totalcount", action="store_true",
                              help="""count each element in a text and rank them 
                                        by total count""")
    
    count_parser.add_argument("-c", "--count", metavar="ELEMENT", type=str,
                              help="""count the number of times ELEMENT appears
                              in the text.""")
    
    
    
    match_parser = subparsers.add_parser("match", help=
                                           """count the number of matches of a 
                                           pattern within each one of the 
                                           elements of the text""",
                                           parents=[type_parent_parser,
                                                     show_parent_parser])
    
    match_parser.add_argument("patterns", metavar="PATTERN1~PATTERN2~...",
                              type=str,
                              help="""patterns, separated by ~, to match within 
                              the elements.""")
    
    
    info_parser = subparsers.add_parser("info", help=
                                          """get general info about the text""")
    
    info_parser.add_argument("-g", "--general", action="store_true",
                             help="""generate a general info printout about the 
                             text.""")
    
    info_parser.add_argument("-t", "--test", choices=["g"],
                             help="""test the readability of the text using 
                             various readability tests. g for Gunning-Fog Index""")
    
    
    batch_parser = subparsers.add_parser("batch", 
                                         help="""run many commands, at once, 
                                         specified in settings.ini. Look at .ini
                                          file and write => -b example <= in 
                                          the command line to see how it works.
                                          """)
    batch_parser.add_argument("-r", "--run", metavar="BATCH_NAME",
                              help="""Run the specified batch grouping.""")
    
    batch_parser.add_argument("-l", "--list", action="store_true",
                              help="""List all available batch groupings.""")
    
    
    return main_parser

def set_logging_level(bool_option):
    if bool_option:
        logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
        
    else:
        logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

def get_filenames(filename_in):
    
    (name, extension) = filename_in.split(".")
    filename_out = name + "_out" + "." + extension
    
    return (filename_in, filename_out)

def get_output(text, args, config):
    def expand_type(code):
        """Expands one letter element type code to full word"""
        if code == 'c':
            return "characters"
        elif code == 'w':
            return "words"
        elif code == 's':
            return "sentences"
        
        else:
            logging.error("No such element type cannot expand: " + code)
            sys.exit(0)
    
    def get_syllable_pattern(name):
        #Shakespeare Sonnet
        if name == 's':
            return get_repeat_syllable_pattern(10, 14)
        #Haiku
        elif name == 'h':
            return [7,5,7]

    def get_repeat_syllable_pattern(number_of_syllables, times_to_repeat):
        repeat_pattern = []
        for i in range(0, times_to_repeat):
            repeat_pattern.append(number_of_syllables)
        
        return repeat_pattern
    
    commands = ['poem', 'count', 'match', 'info', 'batch']

    if args.command == commands[1]:
        if args.count:
            (element_type, element_to_count) = (expand_type(args.type) , args.count)
            return get_count_output(text, element_type, element_to_count)
        
        elif args.totalcount:
            (element_type, number_to_display) = (expand_type(args.type), args.show)
            return get_totalcount_output(text, element_type, number_to_display)
    
    elif args.command == commands[2]:
        (element_type, elements_to_match,
         number_to_display) = (expand_type(args.type), args.patterns , args.show)
        return get_match_output(text, element_type, elements_to_match, 
                                    number_to_display)
        
    elif args.command == commands[0]:
        
        if args.syllables:
            (syllables_pattern, number_to_generate) = (args.syllables, args.show)
        
        elif args.preset:
            (syllables_pattern, number_to_generate) = (get_syllable_pattern(args.preset), args.show)
            
        elif args.shortcut:
            (syllables_pattern, number_to_generate) = (get_repeat_syllable_pattern(args.shortcut[0], args.shortcut[1]), args.show)
        
        return get_poem_output(text, syllables_pattern, number_to_generate)
        
    elif args.command == commands[3]:
        if args.general:
            logging.error("info -g not implemented")
            sys.exit(0)
        
        elif args.test == 'g':
            test = args.test
            return get_readability_test_output(text, test)
    
    elif args.command == commands[4]:
        module_name = sys.argv[0]
        if args.run:
            if args.run in config:
                output_lines = []
                for batch_args in get_batch_args_list(config, args.run):
                    command = "python " + module_name + " " + args.file_in + " " + batch_args
                    
                    process1 = subprocess.Popen("echo " + command, stdout=subprocess.PIPE)
                    for line in process1.stdout:
                        output_lines.append(line.rstrip().decode("utf-8"))
                    
                    process2 = subprocess.Popen(command, stdout=subprocess.PIPE)
                    for line in process2.stdout:
                        output_lines.append(line.rstrip().decode("utf-8"))
                    
                    output_lines.append(" ")
                
                return output_lines
            
            else:
                logging.error("No such batch grouping : " + args.run )
                sys.exit(0)
        
        if args.list:
            ignore_list = ['DEFAULT', 'parser']
            output_lines = []
            for possible_batch_grouping in config:
                if possible_batch_grouping not in ignore_list:
                    output_lines.append(possible_batch_grouping)
            
            return output_lines


def get_readability_test_output(text, test):
    if test == 'g':
        return get_Gunning_output(text)
    
def get_totalcount_output(text, element_type, number_to_display):
    ranked_elements = text.rank_by_total_count(element_type)

    return generate_ranked_list_output(ranked_elements, number_to_display)

def get_count_output(text, element_type, element_to_count):
    output = []
    
    output.append(text.count_occurences(element_to_count, element_type))
    return output

def get_match_output(text, element_type, elements_to_match, number_to_display):
    match_seperator = "~"
    
    if match_seperator in elements_to_match:
        elements_to_match = elements_to_match.split(match_seperator)
    else:
        elements_to_match = [elements_to_match]
                
    ranked_elements = text.rank_by_number_of_matches( elements_to_match , element_type )
    
    return generate_ranked_list_output(ranked_elements, number_to_display)

def generate_ranked_list_output(rank_list, number_to_show):
    
    def get_last_index_for_output(ranked_elements, number_to_display):
        if len(ranked_elements) < number_to_display:
            return len(ranked_elements)
        else:
            return number_to_display
    
    last_index = get_last_index_for_output(rank_list, number_to_show)
    
    output_lines = []
    for i in range(0, last_index):
        (element, count) = rank_list[i]
        
        if count != 0:
            output_lines.append(str(count) + ": " + str(element) + "\n")
    
    return output_lines

def get_Gunning_output(text):
    return [text.calculate_Gunning_Fog_Index()]

def get_poem_output(text, syllables_pattern, number_to_generate):
    output_lines = []
    
    poems = text.generate_poems(syllables_pattern, number_to_generate)
    for poem in poems:
        for line in poem:
            output_lines.append(line + "\n")
        
        output_lines.append("\n")
    
    return output_lines


def output_to_console(output_lines):
    for line in output_lines:
        print(line)

def output_to_file(filename, output_lines):
    with io.open(filename, 'w') as file:
        file.writelines(output_lines)

if __name__== "__main__":
        main()
#               
#        cProfile.run("main()", "main_stats.prof")
#        
#        p = pstats.Stats('main_stats.prof')
#        p.strip_dirs().sort_stats('time').print_stats(5)