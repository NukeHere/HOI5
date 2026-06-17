import arcade
import random
from MainGame import Game
from pyglet.graphics import Batch


class StartView(arcade.View):
    def on_show(self):
        """Настройка начального экрана"""
        arcade.set_background_color(arcade.color.BLACK)

    def on_draw(self):
        """Отрисовка начального экрана"""
        self.clear()
        # Батч для текста
        self.batch = Batch()
        start_text = arcade.Text("Тетрис", self.window.width / 2, self.window.height / 2,
                                 arcade.color.WHITE, font_size=50, anchor_x="center", batch=self.batch)
        any_key_text = arcade.Text("Any key to start",
                                   self.window.width / 2, self.window.height / 2 - 75,
                                   arcade.color.GRAY, font_size=20, anchor_x="center", batch=self.batch)
        self.batch.draw()

    def on_key_press(self, key, modifiers):
        """Начало игры при нажатии клавиши"""
        game_view = Game()
        self.window.show_view(game_view)


def main():
    window = arcade.Window(1200, 800, "Тетрис")
    start_view = StartView()
    window.show_view(start_view)
    arcade.run()


if __name__ == "__main__":
    main()
