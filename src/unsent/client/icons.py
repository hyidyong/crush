import math
import pygame

def icon_surface(name,size,color,filled=False):
    s=pygame.Surface((size,size),pygame.SRCALPHA);k=size/24;line=max(1,round(1.8*k))
    def pts(values):return [(round(x*k),round(y*k)) for x,y in values]
    def path(values,close=False):pygame.draw.lines(s,color,close,pts(values),line)
    def rect(x,y,w,h,r=0,width=line):pygame.draw.rect(s,color,pygame.Rect(round(x*k),round(y*k),round(w*k),round(h*k)),width,border_radius=round(r*k))
    def circle(x,y,r,width=line):pygame.draw.circle(s,color,(round(x*k),round(y*k)),round(r*k),width)
    if name=='back':path([(15,3),(6,12),(15,21)])
    elif name=='down':path([(4,8),(12,16),(20,8)])
    elif name=='close':path([(5,5),(19,19)]);path([(19,5),(5,19)])
    elif name=='search':circle(10,10,7);path([(15,15),(22,22)])
    elif name=='more':
        for x in (5,12,19):circle(x,12,1.5,0)
    elif name=='compose':
        path([(11,4),(5,4),(3,6),(3,20),(5,22),(19,22),(21,20),(21,13)])
        path([(9,15),(10,10),(18,2),(22,6),(14,14),(9,15)]);path([(17,3),(21,7)])
    elif name=='home':
        path([(3,10),(12,2),(21,10),(21,21),(15,21),(15,14),(9,14),(9,21),(3,21),(3,10)])
    elif name in ('plane','send'):
        points=pts([(2,3),(22,2),(14,22),(10,13),(2,3)])
        pygame.draw.polygon(s,color,points,0 if filled else line);path([(10,13),(22,2)])
    elif name=='heart':
        points=[(12,21),(3,12),(2,8),(4,4),(8,3),(12,7),(16,3),(20,4),(22,8),(21,12),(12,21)]
        pygame.draw.polygon(s,color,pts(points),0 if filled else line)
    elif name=='comment':circle(11,11,9);path([(16,18),(22,22),(21,15)])
    elif name=='bookmark':path([(5,2),(19,2),(19,22),(12,16),(5,22),(5,2)])
    elif name=='camera':
        rect(2,6,20,15,4);path([(6,6),(8,2),(16,2),(18,6)]);circle(12,13,5)
    elif name=='repost':
        path([(5,15),(5,7),(18,7)]);path([(14,3),(18,7),(14,11)])
        path([(19,10),(19,18),(6,18)]);path([(10,14),(6,18),(10,22)])
    elif name=='grid':
        for y in (3,10,17):
            for x in (3,10,17):rect(x,y,4,4,1,0)
    elif name=='tag':
        path([(4,22),(4,6),(9,6),(12,2),(15,6),(20,6),(20,22),(4,22)])
        circle(12,11,3);pygame.draw.arc(s,color,pygame.Rect(round(7*k),round(15*k),round(10*k),round(7*k)),0,math.pi,line)
    elif name=='reels':
        rect(2,2,20,20,5);path([(2,8),(22,8)]);path([(6,2),(10,8)]);path([(14,2),(18,8)]);path([(10,12),(16,15),(10,19),(10,12)])
    else:circle(12,12,8)
    return s
