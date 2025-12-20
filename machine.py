import pygame as pg

class Machine:
    def __init__(self, 
                 max_speed, accel, brake, friction, steer_speed,
                 shift_max, shift_inc, shift_decay, shift_min,
                 gravity, jump_force, air_drag, hard_landing_penalty,
                 hull_points, canopy_points, hull_color, edge_color, canopy_color):
        # Physics
        self.max_speed = max_speed
        self.accel = accel
        self.brake = brake
        self.friction = friction
        self.steer_speed = steer_speed
        
        # Jumping/Landing
        self.gravity = gravity
        self.jump_force = jump_force
        self.air_drag = air_drag
        self.hard_landing_penalty = hard_landing_penalty
        
        # Shift/Strafe
        self.shift_max = shift_max
        self.shift_inc = shift_inc
        self.shift_decay = shift_decay
        self.shift_min = shift_min
        
        # Visuals (Vector)
        self.hull_points = [pg.Vector2(p) for p in hull_points]
        self.canopy_points = [pg.Vector2(p) for p in canopy_points]
        self.hull_color = hull_color
        self.edge_color = edge_color
        self.canopy_color = canopy_color

    def draw(self, screen, center, lean):
        hull_pts = [center + p.rotate_rad(lean) for p in self.hull_points]
        canopy_pts = [center + p.rotate_rad(lean) for p in self.canopy_points]

        pg.draw.polygon(screen, self.hull_color, hull_pts)
        pg.draw.polygon(screen, self.edge_color, hull_pts, width=2)
        pg.draw.polygon(screen, self.canopy_color, canopy_pts)


# Instance with current settings
DOPAMINE_FALCON = Machine(
    max_speed=0.12,
    accel=0.003,
    brake=0.01,
    friction=0.0008,
    steer_speed=0.015,
    shift_max=0.15,
    shift_inc=0.005,
    shift_decay=0.0025,
    shift_min=0.005,
    gravity=0.0005,
    jump_force=0.015,
    air_drag=0.0004,
    hard_landing_penalty=0.5,
    hull_points=[(0, -50), (28, 18), (0, 30), (-28, 18)],
    canopy_points=[(0, -30), (10, 4), (-10, 4)],
    hull_color=(60, 180, 255),
    edge_color=(15, 35, 80),
    canopy_color=(255, 255, 255)
)
