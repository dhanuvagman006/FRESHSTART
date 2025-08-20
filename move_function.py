
Allowed_directions = {"front","back","left","right"}


def robot_leg_movement(command: str):
    """Dispatch leg movement. Returns status string."""
    if not isinstance(command, str):
        return "invalid argument type"
    cmd = command.strip().lower()
    if cmd == 'forward':
        cmd = 'front'
    if cmd not in Allowed_directions:
        return "not valid argument use: front|back|left|right"
    if cmd == 'front':
        return move_front()
    if cmd == 'back':
        return move_back()
    if cmd == 'left':
        return move_left()
    if cmd == 'right':
        return move_right()

def move_front():
    print("Move Front")
    return "front:ok"

def move_back():
    print("Move Back")
    return "back:ok"

def move_left():
    print("Move Left")
    return "left:ok"

def move_right():
    print("Move Right")
    return "right:ok"
