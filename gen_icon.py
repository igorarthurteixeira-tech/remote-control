from PIL import Image, ImageDraw

def make_icon(size=256):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    s   = size / 64
    d.ellipse([int(2*s), int(2*s), int(62*s), int(62*s)], fill='#7c3aed')
    d.arc([int(14*s), int(10*s), int(50*s), int(46*s)], 210, 330, fill='white', width=max(3, int(5*s)))
    d.arc([int(22*s), int(18*s), int(42*s), int(38*s)], 210, 330, fill='white', width=max(2, int(4*s)))
    d.ellipse([int(28*s), int(34*s), int(36*s), int(42*s)], fill='white')
    return img

if __name__ == '__main__':
    sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
    make_icon(256).save('icon.ico', sizes=sizes)
    print('icon.ico gerado.')
