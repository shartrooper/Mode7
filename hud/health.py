import pygame as pg

class HealthHUD:
    """
    Modular HUD component for rendering Health, Overshield, and Screen Feedback.
    """
    def __init__(self, size=(320, 20), margins=(20,20)):
        self.size = size
        self.margins = margins
        
        # Color Palette
        self.color_health_high = (40, 220, 110)
        self.color_health_mid = (240, 200, 40)
        self.color_health_low = (230, 50, 60)
        self.color_overshield = (30, 210, 255)
        self.color_bg = (10, 12, 20)
        self.color_border = (180, 200, 220)
        self.color_text = (240, 240, 240)
        
        pg.font.init()
        try:
            self.font = pg.font.SysFont("Consolas", 18, bold=True)
        except Exception:
            self.font = None

    def get_main_rect(self,screen):
        """
            Calculates and returns the main health bar bounding rect
            Anchored to the Top-Right of the active screen.
        """
        margin_right, margin_top = self.margins
        screen_w = screen.get_width()
        rect= pg.Rect((0,0), self.size)
        # Bar HUD positioning
        rect.topright = (screen_w - margin_right, margin_top)
        return rect

    def draw(self, screen, health, max_health, shield, max_shield):
        """
        Draws the Top Right Anchored Health bar and stacked Overshield bar.
        
        :param screen: Pygame target surface to draw onto
        :param health: Current main health value
        :param max_health: Maximum main health capacity
        :param shield: Current overshield value
        :param max_shield: Maximum overshield capacity
        """
        main_rect = self.get_main_rect(screen)

        # Main BG
        pg.draw.rect(screen, self.color_bg, main_rect, border_radius=4)

        # Health and Fill rect
        hp_ratio = max(0.0, health / max_health)
        fill_w = int(main_rect.width * hp_ratio)

        if hp_ratio > 0.5:
            fill_col = self.color_health_high
        elif hp_ratio > 0.25:
            fill_col = self.color_health_mid
        else:
            fill_col = self.color_health_low

        if fill_w > 0:
            fill_rect = pg.Rect(main_rect.x, main_rect.y, fill_w, main_rect.height)
            pg.draw.rect(screen, fill_col, fill_rect, border_radius=4)

        # Segment dividers
        num_segments = 10
        for i in range(1, num_segments):
            seg_x = main_rect.x + (main_rect.width // num_segments) * i
            pg.draw.line(screen,self.color_bg, (seg_x, main_rect.y), (seg_x, main_rect.bottom -  1), 2)

        # Main outer border
        pg.draw.rect(screen, self.color_border, main_rect, width=2, border_radius=4)

        # Overshield Bar (Just anchored beneath main_rect)
        shield_h = 10
        shield_rect = pg.Rect(main_rect.x, main_rect.bottom + 6, main_rect.width, shield_h)

        pg.draw.rect(screen, self.color_bg, shield_rect, border_radius=3)

        shield_ratio = max(0.0, shield / max_shield)
        shield_fill_w = int(shield_rect.width * shield_ratio)

        if shield_fill_w > 0:
            shield_fill_rect = pg.Rect(shield_rect.x, shield_rect.y, shield_fill_w, shield_rect.height)
            pg.draw.rect(screen, self.color_overshield, shield_fill_rect, border_radius=3)
            for i in range(1, 5):
                seg_x = shield_rect.x + (shield_rect.width // 5) * i
                pg.draw.line(screen, self.color_bg, (seg_x, shield_rect.y), (seg_x, shield_rect.bottom - 1), 1)

        border_col = self.color_overshield if shield > 0 else (60, 70, 90)
        pg.draw.rect(screen, border_col, shield_rect, width=1, border_radius=3)

    def draw_warning_overlay(self, screen, health, max_health):
        """
        Draws screen-space low health vignette warning overlay when health is critical (<25%).
        """
        if health < max_health * 0.25:
            # Low health red pulse/border logic
            warning_surf = pg.Surface(screen.get_size(), pg.SRCALPHA)
            pg.draw.rect(warning_surf, (230, 30, 40, 60), warning_surf.get_rect(), width=14)
            screen.blit(warning_surf, (0, 0))
