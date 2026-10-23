def classify_release(x,y,at,end_x,end_y,end_at,dragged=False):
    if dragged or abs(end_x-x)>8 or abs(end_y-y)>8:return 'none'
    return 'long_press' if end_at-at>=.5 else 'click'
def carousel_swipe(start,end):
    dx=end[0]-start[0];dy=end[1]-start[1]
    return (-1 if dx>0 else 1) if abs(dx)>=32 and abs(dx)>abs(dy)*1.5 else 0
