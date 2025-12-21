import pygame as pg
import sys
from settings import WIN_RES, FPS
from mode7 import Mode7


class App:
    def __init__(self):
        pg.init()
        self.screen = pg.display.set_mode(WIN_RES)
        self.clock = pg.time.Clock()
        self.dt = 1.0
        self.mode7 = Mode7(self)

    def update(self):
        # delta time in seconds, normalized to 60 FPS
        self.dt = self.clock.tick(FPS) * 0.001 * 60
        self.mode7.update(self.dt)
        pg.display.set_caption(f'{self.clock.get_fps() : .1f}')

    def draw(self):
        self.mode7.draw()
        pg.display.flip()

    def get_time(self):
        self.time = pg.time.get_ticks() * 0.001

    def check_event(self):
        for i in pg.event.get():
            if i.type == pg.QUIT or (i.type == pg.KEYDOWN and i.key == pg.K_ESCAPE):
                pg.quit()
                sys.exit()

    def run(self):
        while True:
            self.check_event()
            self.get_time()
            self.update()
            self.draw()


if __name__ == '__main__':
    app = App()
    app.run()
