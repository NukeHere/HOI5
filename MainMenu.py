from dataclasses import dataclass
from typing import Callable

import arcade

from MainGame import Game


RESOLUTIONS = [(1024, 768), (1200, 800), (1366, 768), (1600, 900), (1920, 1080)]
DIFFICULTIES = ["Легкая", "Обычная", "Сложная"]
BOT_COUNTS = list(range(0, 13))
MAP_SIZES = [50, 75, 100, 125, 150]


@dataclass
class Button:
    label: str
    x: float
    y: float
    width: float
    height: float
    action: Callable[[], None]
    enabled: bool = True

    def contains(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def draw(self, hovered=False):
        if not self.enabled:
            fill = (45, 48, 54)
            border = (78, 82, 90)
            text = (135, 140, 150)
        elif hovered:
            fill = (63, 86, 116)
            border = (165, 195, 230)
            text = arcade.color.WHITE
        else:
            fill = (42, 55, 72)
            border = (100, 126, 155)
            text = (225, 232, 240)

        arcade.draw_lbwh_rectangle_filled(self.x, self.y, self.width, self.height, fill)
        arcade.draw_lbwh_rectangle_outline(self.x, self.y, self.width, self.height, border, 2)
        arcade.draw_text(
            self.label,
            self.x + self.width / 2,
            self.y + self.height / 2,
            text,
            18,
            anchor_x="center",
            anchor_y="center",
        )


@dataclass
class Slider:
    label: str
    x: float
    y: float
    width: float
    value: float
    on_change: Callable[[float], None]

    height: float = 28

    def contains(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def set_from_mouse(self, x):
        self.value = max(0.0, min(1.0, (x - self.x) / self.width))
        self.on_change(self.value)

    def draw(self):
        arcade.draw_text(self.label, self.x, self.y + 42, (225, 232, 240), 16)
        arcade.draw_text(f"{int(self.value * 100)}%", self.x + self.width, self.y + 42, (180, 192, 205), 16,
                         anchor_x="right")
        arcade.draw_lbwh_rectangle_filled(self.x, self.y + 11, self.width, 6, (55, 66, 78))
        arcade.draw_lbwh_rectangle_filled(self.x, self.y + 11, self.width * self.value, 6, (109, 155, 210))
        knob_x = self.x + self.width * self.value
        arcade.draw_circle_filled(knob_x, self.y + 14, 10, (230, 238, 248))


@dataclass
class Dropdown:
    key: str
    label: str
    options: list[str]
    selected_index: int
    x: float
    y: float
    width: float
    height: float
    on_select: Callable[[int], None]
    hovered_index: int | None = None
    scroll_offset: int = 0
    max_visible_options: int = 6

    def contains_header(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def visible_count(self):
        return min(len(self.options), self.max_visible_options)

    def max_scroll_offset(self):
        return max(0, len(self.options) - self.visible_count())

    def opens_up(self):
        return self.y - self.height * self.visible_count() < 24

    def clamp_scroll(self):
        self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll_offset()))

    def scroll(self, amount):
        self.scroll_offset += int(amount)
        self.clamp_scroll()

    def option_at(self, x, y):
        if not (self.x <= x <= self.x + self.width):
            return None

        self.clamp_scroll()
        opens_up = self.opens_up()
        for visible_index in range(self.visible_count()):
            option_index = self.scroll_offset + visible_index
            if opens_up:
                option_y = self.y + self.height * (visible_index + 1)
            else:
                option_y = self.y - self.height * (visible_index + 1)
            if option_y <= y <= option_y + self.height:
                return option_index
        return None

    def draw(self, is_open=False):
        list_width = self.width
        arcade.draw_text(self.label, self.x, self.y + self.height + 8, (225, 232, 240), 16)
        arcade.draw_lbwh_rectangle_filled(self.x, self.y, self.width, self.height, (42, 55, 72))
        arcade.draw_lbwh_rectangle_outline(self.x, self.y, self.width, self.height, (100, 126, 155), 2)
        arcade.draw_text(
            self.options[self.selected_index],
            self.x + 14,
            self.y + self.height / 2,
            (225, 232, 240),
            17,
            anchor_y="center",
        )
        arcade.draw_text("v", self.x + self.width - 18, self.y + self.height / 2, (180, 192, 205), 16,
                         anchor_x="center", anchor_y="center")

        if is_open:
            self.clamp_scroll()
            opens_up = self.opens_up()
            list_height = self.height * self.visible_count()
            list_y = self.y + self.height if opens_up else self.y - list_height
            arcade.draw_lbwh_rectangle_filled(self.x, list_y, list_width, list_height, (31, 41, 53))
            arcade.draw_lbwh_rectangle_outline(self.x, list_y, list_width, list_height, (80, 102, 128), 2)

            for visible_index in range(self.visible_count()):
                index = self.scroll_offset + visible_index
                option = self.options[index]
                if opens_up:
                    option_y = self.y + self.height * (visible_index + 1)
                else:
                    option_y = self.y - self.height * (visible_index + 1)
                if index == self.hovered_index:
                    fill = (54, 72, 94)
                elif index == self.selected_index:
                    fill = (63, 86, 116)
                else:
                    fill = (31, 41, 53)
                arcade.draw_lbwh_rectangle_filled(self.x + 1, option_y, list_width - 2, self.height, fill)
                if visible_index > 0:
                    arcade.draw_line(self.x, option_y, self.x + list_width, option_y, (80, 102, 128), 1)
                arcade.draw_text(option, self.x + 14, option_y + self.height / 2, (225, 232, 240), 16,
                                 anchor_y="center")

            if self.max_scroll_offset() > 0:
                track_x = self.x + list_width - 7
                thumb_height = max(18, list_height * self.visible_count() / len(self.options))
                scroll_range = max(1, self.max_scroll_offset())
                thumb_space = list_height - thumb_height
                if opens_up:
                    thumb_y = list_y + thumb_space * (1 - self.scroll_offset / scroll_range)
                else:
                    thumb_y = list_y + thumb_space * (1 - self.scroll_offset / scroll_range)
                arcade.draw_lbwh_rectangle_filled(track_x, list_y + 4, 3, list_height - 8, (64, 77, 92))
                arcade.draw_lbwh_rectangle_filled(track_x - 2, thumb_y + 4, 7, thumb_height - 8, (150, 170, 194))


class MainMenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.screen = "main"
        self.hovered_button = None
        self.active_slider = None
        self.open_dropdown = None
        self.buttons = []
        self.sliders = []
        self.dropdowns = []
        self.message = ""

        self.sound_volume = 0.8
        self.music_volume = 0.6
        self.fullscreen = False
        self.resolution_index = 1
        self.pending_fullscreen = self.fullscreen
        self.pending_resolution_index = self.resolution_index

        self.difficulty_index = 1
        self.bot_count_index = 4
        self.map_size_index = 2

    def on_show(self):
        arcade.set_background_color((13, 18, 24))
        self.rebuild_layout()

    def on_resize(self, width, height):
        super().on_resize(width, height)
        self.rebuild_layout()

    def rebuild_layout(self):
        if not self.window:
            return

        self.buttons = []
        self.sliders = []
        self.dropdowns = []
        if self.screen == "main":
            self.build_main_menu()
        elif self.screen == "settings":
            self.build_settings_menu()
        elif self.screen == "new_game":
            self.build_new_game_menu()
        elif self.screen == "help":
            self.build_help_menu()

    def button(self, label, x, y, width, height, action, enabled=True):
        self.buttons.append(Button(label, x, y, width, height, action, enabled))

    def dropdown(self, key, label, options, selected_index, x, y, width, height, on_select):
        self.dropdowns.append(Dropdown(key, label, options, selected_index, x, y, width, height, on_select))

    def build_main_menu(self):
        x = self.window.width / 2 - 150
        y = self.window.height / 2 + 110
        gap = 54
        self.button("Новая игра", x, y, 300, 42, lambda: self.set_screen("new_game"))
        self.button("Продолжить игру", x, y - gap, 300, 42, self.continue_game)
        self.button("Мультиплеер", x, y - gap * 2, 300, 42, self.multiplayer)
        self.button("Настройки", x, y - gap * 3, 300, 42, self.enter_settings)
        self.button("Помощь", x, y - gap * 4, 300, 42, lambda: self.set_screen("help"))
        self.button("Выход из игры", x, y - gap * 5, 300, 42, self.exit_game)

    def build_settings_menu(self):
        panel_x = self.window.width / 2 - 230
        top = self.window.height / 2 + 130
        self.sliders.append(Slider("Громкость звука", panel_x, top - 70, 460, self.sound_volume, self.set_sound_volume))
        self.sliders.append(Slider("Громкость музыки", panel_x, top - 140, 460, self.music_volume, self.set_music_volume))
        self.button(f"Полный экран: {'Вкл' if self.pending_fullscreen else 'Выкл'}", panel_x, top - 210, 220, 42,
                    self.toggle_pending_fullscreen)
        resolution_options = [f"{width}x{height}" for width, height in RESOLUTIONS]
        self.dropdown("resolution", "Разрешение", resolution_options, self.pending_resolution_index,
                      panel_x + 240, top - 210, 220, 42, self.set_pending_resolution)
        self.button("Применить", panel_x, top - 285, 220, 44, self.apply_settings)
        self.button("Назад", panel_x + 240, top - 285, 220, 44, lambda: self.set_screen("main"))

    def build_new_game_menu(self):
        panel_x = self.window.width / 2 - 230
        top = self.window.height / 2 + 130
        self.dropdown("difficulty", "Сложность", DIFFICULTIES, self.difficulty_index,
                      panel_x, top - 55, 460, 42, self.set_difficulty)
        self.dropdown("bots", "Количество ботов", [str(count) for count in BOT_COUNTS], self.bot_count_index,
                      panel_x, top - 130, 460, 42, self.set_bot_count)
        self.dropdown("map_size", "Размер карты",
                      [f"{size}x{size}" for size in MAP_SIZES], self.map_size_index,
                      panel_x, top - 205, 460, 42, self.set_map_size)
        self.button("Начать игру", panel_x, top - 300, 220, 46, self.start_new_game)
        self.button("Назад", panel_x + 240, top - 300, 220, 46, lambda: self.set_screen("main"))

    def build_help_menu(self):
        panel_x = self.window.width / 2 - 230
        self.button("Назад", panel_x, self.window.height / 2 - 210, 220, 44, lambda: self.set_screen("main"))

    def set_screen(self, screen):
        self.screen = screen
        self.hovered_button = None
        self.active_slider = None
        self.open_dropdown = None
        self.message = ""
        self.rebuild_layout()

    def enter_settings(self):
        self.pending_fullscreen = self.fullscreen
        self.pending_resolution_index = self.resolution_index
        self.set_screen("settings")

    def set_sound_volume(self, value):
        self.sound_volume = value

    def set_music_volume(self, value):
        self.music_volume = value

    def toggle_pending_fullscreen(self):
        self.pending_fullscreen = not self.pending_fullscreen
        self.rebuild_layout()

    def set_pending_resolution(self, index):
        self.pending_resolution_index = index
        self.rebuild_layout()

    def apply_settings(self):
        self.fullscreen = self.pending_fullscreen
        self.resolution_index = self.pending_resolution_index
        width, height = RESOLUTIONS[self.resolution_index]
        self.window.set_fullscreen(self.fullscreen)
        if not self.fullscreen:
            self.window.set_size(width, height)
        self.message = "Настройки применены."
        self.rebuild_layout()

    def set_difficulty(self, index):
        self.difficulty_index = index
        self.rebuild_layout()

    def set_bot_count(self, index):
        self.bot_count_index = index
        self.rebuild_layout()

    def set_map_size(self, index):
        self.map_size_index = index
        self.rebuild_layout()

    def continue_game(self):
        self.message = "Сохранений пока нет."

    def multiplayer(self):
        self.message = "Мультиплеер пока не доступен."

    def exit_game(self):
        arcade.exit()

    def start_new_game(self):
        game_view = Game(
            difficulty=DIFFICULTIES[self.difficulty_index],
            bot_count=BOT_COUNTS[self.bot_count_index],
            map_size=MAP_SIZES[self.map_size_index],
        )
        self.window.show_view(game_view)

    def on_draw(self):
        self.clear()
        self.draw_background()
        if self.screen == "main":
            self.draw_title("HOI 5")
        elif self.screen == "settings":
            self.draw_title("Настройки")
        elif self.screen == "new_game":
            self.draw_title("Новая игра")
        elif self.screen == "help":
            self.draw_title("Помощь")
            self.draw_help_text()

        for slider in self.sliders:
            slider.draw()

        for button in self.buttons:
            button.draw(button == self.hovered_button)

        for dropdown in self.dropdowns:
            if dropdown.key != self.open_dropdown:
                dropdown.draw(False)
        for dropdown in self.dropdowns:
            if dropdown.key == self.open_dropdown:
                dropdown.draw(True)

        if self.message:
            arcade.draw_text(self.message, self.window.width / 2, 44, (220, 180, 90), 16,
                             anchor_x="center", anchor_y="center")

    def draw_background(self):
        arcade.draw_lbwh_rectangle_filled(0, 0, self.window.width, self.window.height, (13, 18, 24))
        arcade.draw_lbwh_rectangle_filled(0, 0, self.window.width, 88, (20, 29, 38))
        arcade.draw_lbwh_rectangle_filled(0, self.window.height - 96, self.window.width, 96, (20, 29, 38))

    def draw_title(self, title):
        arcade.draw_text(title, self.window.width / 2, self.window.height - 58, arcade.color.WHITE, 36,
                         anchor_x="center", anchor_y="center", bold=True)

    def draw_help_text(self):
        text = (
            "Стрелки двигают камеру.\n"
            "Правая кнопка мыши перетаскивает карту.\n"
            "Колесико мыши приближает карту к курсору.\n"
            "Левая кнопка мыши выбирает тайл."
        )
        arcade.draw_text(text, self.window.width / 2 - 230, self.window.height / 2 + 90,
                         (210, 220, 230), 17, width=460, multiline=True)

    def on_mouse_motion(self, x, y, dx, dy):
        self.hovered_button = None
        if self.open_dropdown:
            for dropdown in self.dropdowns:
                if dropdown.key == self.open_dropdown:
                    dropdown.hovered_index = dropdown.option_at(x, y)
                    break
            return

        for button in self.buttons:
            if button.contains(x, y):
                self.hovered_button = button
                break

    def on_mouse_press(self, x, y, button, modifiers):
        if button != arcade.MOUSE_BUTTON_LEFT:
            return

        for dropdown in self.dropdowns:
            if dropdown.key == self.open_dropdown:
                option_index = dropdown.option_at(x, y)
                if option_index is not None:
                    self.open_dropdown = None
                    dropdown.hovered_index = None
                    dropdown.on_select(option_index)
                    return

        for dropdown in self.dropdowns:
            if dropdown.contains_header(x, y):
                self.open_dropdown = None if self.open_dropdown == dropdown.key else dropdown.key
                dropdown.hovered_index = None
                return

        for dropdown in self.dropdowns:
            dropdown.hovered_index = None
        self.open_dropdown = None

        for slider in self.sliders:
            if slider.contains(x, y):
                self.active_slider = slider
                slider.set_from_mouse(x)
                return

        for menu_button in self.buttons:
            if menu_button.enabled and menu_button.contains(x, y):
                menu_button.action()
                return

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self.active_slider and buttons & arcade.MOUSE_BUTTON_LEFT:
            self.active_slider.set_from_mouse(x)

    def on_mouse_release(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.active_slider = None

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        if not self.open_dropdown:
            return

        for dropdown in self.dropdowns:
            if dropdown.key == self.open_dropdown:
                dropdown.scroll(-scroll_y)
                dropdown.hovered_index = dropdown.option_at(x, y)
                return

    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE and self.open_dropdown:
            for dropdown in self.dropdowns:
                dropdown.hovered_index = None
            self.open_dropdown = None
        elif key == arcade.key.ESCAPE and self.screen != "main":
            self.set_screen("main")


def main():
    window = arcade.Window(1200, 800, "HOI 5")
    start_view = MainMenuView()
    window.show_view(start_view)
    arcade.run()


if __name__ == "__main__":
    main()
