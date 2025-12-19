# settings
WIN_RES = WIDTH, HEIGHT = 800, 600
HALF_WIDTH, HALF_HEIGHT = WIDTH // 2, HEIGHT // 2
FOCAL_LEN = 140 #from 140

# renderer tuning mirrored from mode7-racer
STD_HORIZON = HALF_HEIGHT // 2
CAM_DISTANCE = 4
SCALE = 48
FOG_DENSITY = 120
BACKGROUND_ROTATION_SPEED = 120

# camera altitude keeps us glued to the track
CAM_ALT = 0.9

# Framerate Cap
FPS = 60

# player tuning constants
# Starting position is 1640 x 550 divided by scale
PLAYER_START_POS = (550 / SCALE, 1640 / SCALE)
PLAYER_MAX_SPEED = 0.12
PLAYER_ACCEL = 0.003
PLAYER_BRAKE = 0.01
PLAYER_FRICTION = 0.0008
PLAYER_STEER_SPEED = 0.015

# Strafing/Shift weight
SHIFT_MAX_FORCE = 0.15
SHIFT_INCREASE = 0.005
SHIFT_DECAY = 0.0025
SHIFT_MIN_SPEED = 0.005