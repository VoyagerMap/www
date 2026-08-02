import sys
from PIL import Image
FULL_W, SMALL_W, JPG_Q, WEBP_Q = 1080, 800, 82, 80
def rz(im,w):
    return im if im.width==w else im.resize((w, round(im.height*w/im.width)), Image.LANCZOS)
im = Image.open(sys.argv[1]).convert("RGB")
for w,suf in ((FULL_W,""),(SMALL_W,"-800w")):
    r=rz(im,w)
    r.save(f"{sys.argv[2]}{suf}.jpg","JPEG",quality=JPG_Q,optimize=True,progressive=True)
    r.save(f"{sys.argv[2]}{suf}.webp","WEBP",quality=WEBP_Q,method=6)
    print(f"  {sys.argv[2]}{suf}  {r.width}x{r.height}")
