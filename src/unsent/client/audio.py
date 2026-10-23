def notify():
    try:
        import array,math,pygame
        if pygame.mixer.get_init():
            rate=pygame.mixer.get_init()[0];samples=array.array('h',(int(800*math.sin(2*math.pi*660*i/rate)*(1-i/(rate*.09))) for i in range(int(rate*.09))))
            pygame.mixer.Sound(buffer=samples).play()
    except Exception:pass
