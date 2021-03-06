from argparse import ArgumentParser
from time import sleep
from math import floor
from gamefield import GameField
from keyboard import Keyboard
from display import Display
from colourdisplay import ColourDisplay
from pacman import Pacman
from ghost import Ghost
from wall import Wall
from pill import Pill
from levels import LevelMaps
from scoreboard import Scoreboard

import sys
import os
import tokenizer

FRAME_RATE_IN_SECS = 0.1


class Game(object):
    def __init__(self, input_map=None):
        if input_map is not None:
            self.input_map = input_map.rstrip()
        self.field = None
        self.lives = 3
        self.score = 0
        self.pacman = None
        self.ghosts = []
        self.pills = []
        self.walls = []
        self.game_over = False
        self.controller = None
        self.display = None
        self.gate = None
        self.level = 1
        self.last_level = 1
        self.level_maps = None
        self.animation = False
        self.using_pills = False
        self.player = None
        self.scoreboard = None

    def init(self):
        self.parse()
        self.display.init(self)

    def play(self, debug):
        while True:
            self.tick()
            self.render()
            self.refresh()
            sleep(FRAME_RATE_IN_SECS)
            if (not self.pacman.alive):
                self.display.flash()
                self.pacman.restart()
            if self.game_over or debug:
                break
        self.post_score()

    def parse(self):
        self.set_game_input()
        columns = self.input_map.index("\n")
        self.parse_status(self.input_map[:columns])
        screen_rows = self.input_map[columns+1:].split('\n')
        rows = len(screen_rows)
        self.field = GameField(columns, rows)
        self.parse_field(screen_rows)

    def set_game_input(self):
        if self.level_maps:
            self.input_map = self.level_maps.get_level(self.level)
        else:
            if "SEPARATOR" in self.input_map:
                self.level_maps = LevelMaps(self.input_map)
                self.last_level = self.level_maps.max_level()
                self.input_map = self.level_maps.get_level(self.level)

    def parse_status(self, status_line):
        elements = status_line.split()
        try:
            self.lives = int(elements[0])
            self.score = int(elements[1])
        except ValueError:
            pass

    def parse_field(self, screen_rows):
        for y in range(self.field.height()):
            for x in range(self.field.width()):
                element = tokenizer.get_element((x, y), screen_rows[y][x])
                if (element):
                    element.add_to_game(self)

    def add_pill(self, pill):
        self.using_pills = True
        self.pills.append(pill)
        self.field.add(pill.coordinates, pill)

    def add_ghost(self, ghost):
        self.ghosts.append(ghost)
        self.field.add(ghost.coordinates, ghost)

    def set_field(self, width, height):
        self.field = GameField(width, height)

    def set_pacman(self, coordinates, direction):
        pacman = Pacman(coordinates)
        pacman.set_direction(direction)
        pacman.add_to_game(self)

    def add_pacman(self, pacman):
        self.pacman = pacman
        self.field.add(pacman.coordinates, pacman)

    def add_wall(self, coordinates, icon):
        wall = Wall(coordinates, icon)
        self.walls.append(wall)
        self.field.add(coordinates, wall)
        if Wall.is_gate(wall):
            self.gate = wall

    def tick(self):
        for ghost in self.ghosts:
            ghost.tick()
        if self.pacman:
            self.pacman.tick()
        if self.is_level_clear():
            self.next_level()
        self.update_field()

    def render(self):
        composite = Game.render_status(self.lives,
                                       self.score,
                                       self.field.width())
        self.output = composite["video"]
        self.colour = composite["colour"]
        self.output += "\n"
        self.colour.append(0)
        composite = self.field.render()
        self.output += composite["video"]
        self.colour.extend(composite["colour"])

    def render_status(lives, score, columns):
        colour = []
        video = "{lives:1d}".format(lives=lives)
        video += "{score:>{width}d}".format(score=score,
                                            width=columns - len(video))
        for i in range(len(video)):
            colour.append(0)
        return {"video": video, "colour": colour}

    def refresh(self):
        self.display.refresh(self.output, self.colour)

    def update_field(self):
        new_field = GameField(self.field.width(), self.field.height())
        for wall in self.walls:
            new_field.add(wall.coordinates, wall)
        for pill in self.pills:
            new_field.add(pill.coordinates, pill)
        for ghost in self.ghosts:
            new_field.add(ghost.coordinates, ghost)
        if self.pacman:
            new_field.add(self.pacman.coordinates, self.pacman)
        if self.game_over:
            Game.print_game_over(new_field)
        self.field = new_field

    def get_element(self, coords):
        return self.field.get(coords)

    def is_ghost(self, coordinates):
        return Ghost.is_ghost(self.field.get(coordinates))

    def is_wall(self, coordinates):
        return Wall.is_wall(self.field.get(coordinates))

    def is_gate(self, coordinates):
        return Wall.is_gate(self.field.get(coordinates))

    def is_field(self, coordinates):
        return Wall.is_field(self.field.get(coordinates))

    def is_pill(self, coordinates):
        return Pill.is_pill(self.field.get(coordinates))

    def is_pacman(self, coordinates):
        return isinstance(self.field.get(coordinates), Pacman)

    def eat_pill(self, coordinates):
        pill = self.field.get(coordinates)
        self.pills.remove(pill)
        self.score += pill.score()
        for ghost in self.ghosts:
            ghost.trigger_effect(pill)

    def kill_ghost(self, coordinates):
        ghost = self.field.get(coordinates)
        self.score += ghost.score()
        ghost.kill()

    def kill_pacman(self):
        self.pacman.kill()
        self.lives -= 1
        if (self.lives == 0):
            self.game_over = True

    def get_pacman(self):
        return self.pacman

    def set_controller(self, controller):
        self.controller = controller

    def set_display(self, display):
        self.display = display

    def move(self, direction):
        self.pacman.move(direction)

    def set_level(self, level):
        self.level = level

    def set_max_level(self, level):
        self.last_level = level

    def is_level_clear(self):
        return (len(self.pills) == 0) and self.using_pills

    def next_level(self):
        if self.level < self.last_level:
            self.level += 1
            self.pills[:] = []
            self.walls = []
            self.ghosts = []
            self.parse()
        else:
            self.game_over = True
            self.pacman.restart()

    def use_animation(self):
        self.animation = True

    def get_lives(self):
        return self.lives

    def get_score(self):
        return self.score

    def print_game_over(field):
        cols = field.width()
        rows = field.height()
        GAME = "GAME"
        OVER = "OVER"
        y = floor(rows / 2) - 2
        padding = floor(((cols - 2) - len(GAME)) / 2)
        for i in range(len(GAME)):
            x = padding + i + 1
            field.add((x, y), GAME[i])
            field.add((x, y+1), OVER[i])

    def set_player(self, player):
        self.player = player

    def post_score(self):
        if self.scoreboard is None:
            scoreboard_url = os.getenv("SCOREBOARD_URL")
            self.scoreboard = Scoreboard(scoreboard_url, self.player)
        self.scoreboard.post_score(self.score)

    def get_scores(self):
        response = self.scoreboard.scores()
        scores = []
        for score in response:
            name = score.player
            points = str(score.score)
            scores.append(name + ":" + points)
        return scores


def start_game(file, colour, debug):
    with open(file) as f:
        level_map = f.read()

    game = Game(level_map)
    controller = Keyboard(game)
    if (colour):
        display = ColourDisplay(sys.stdout)
    else:
        display = Display(sys.stdout)
    if (not debug):
        controller.init()
        game.set_controller(controller)
        game.use_animation()
    game.set_player(os.getenv("USER", "python-user"))
    game.set_display(display)
    game.init()
    game.play(debug)
    controller.close()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-f", "--file",
                        help="level map for the game.")
    parser.add_argument("-c", "--colour",
                        help="use colour display.",
                        action="store_true")
    parser.add_argument("-d", "--debug",
                        help="one frame for debug mode.",
                        action="store_true")
    args = parser.parse_args()
    if args.file:
        file = args.file
    else:
        file = "data/pacman.txt"
    start_game(file, args.colour, args.debug)
