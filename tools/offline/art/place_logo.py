"""Puts the Toontown Offline logo (art/toontown-offline-logo.png) over the old
logo in assets/launcher-background.jpg, with a white rim and glow like the old
one had. Needs opencv-python-headless and numpy:

    python place_logo.py LOGO.png OUT.jpg [WIDTH]
"""
import cv2, numpy as np, sys
bg = cv2.imread('/home/claude/ttr-offline-test/assets/launcher-background.jpg')
logo = cv2.imread(sys.argv[1], cv2.IMREAD_UNCHANGED)
out = sys.argv[2]
X0, Y0 = 1620, 0
x1, y1, x2, y2 = X0 + 120, 15, X0 + 1000, 390
reg = bg[y1:y2, x1:x2].astype(int)
b, g, r = reg[..., 0], reg[..., 1], reg[..., 2]
orange = (r > 170) & (r - g > 60) & (b < 120)
yellow = (r > 190) & (g > 170) & (b < 120)
dark = reg.max(axis=2) < 100
grey = (abs(r - g) < 18) & (abs(g - b) < 18) & (r > 100)
m = (orange | yellow | dark | grey).astype(np.uint8) * 255
# Past the logo's right end is the toon's face, which has the same colours.
m[:, X0 + 960 - x1:] = 0
# The white rim round the orange.
near = cv2.dilate(orange.astype(np.uint8) * 255, np.ones((41, 41), np.uint8))
white = (reg.min(axis=2) > 205) & (near > 0)
white[:, X0 + 975 - x1:] = False
m |= white.astype(np.uint8) * 255
# Disney's and the SM mark.
for (ax1, ay1, ax2, ay2) in ((395, 20, 620, 115), (945, 55, 1000, 90)):
    m[ay1 - y1:ay2 - y1, ax1 + X0 - x1:ax2 + X0 - x1] = 255
# Fill holes inside the logo.
flood = m.copy()
h, w = m.shape
cv2.floodFill(flood, np.zeros((h + 2, w + 2), np.uint8), (0, h - 1), 255)
m = m | cv2.bitwise_not(flood)
m = cv2.dilate(m, np.ones((9, 9), np.uint8))
cv2.imwrite(out + '-mask.png', m)
full = np.zeros(bg.shape[:2], np.uint8); full[y1:y2, x1:x2] = m
clean = cv2.inpaint(bg, full, 25, cv2.INPAINT_TELEA)
clean = np.where(full[..., None] > 0, cv2.GaussianBlur(clean, (0, 0), 6), clean)
# The new logo where the old one was, with a white rim and glow like it had.
W = int(sys.argv[3]) if len(sys.argv) > 3 else 860
H = int(round(logo.shape[0] * W / logo.shape[1]))
cx, cy = X0 + 552, 210
small = cv2.GaussianBlur(cv2.resize(logo, (W, H), interpolation=cv2.INTER_AREA), (0, 0), 0.7).astype(float)
pad = 40
canvas = np.zeros((H + 2 * pad, W + 2 * pad, 4)); canvas[pad:pad + H, pad:pad + W] = small
alpha = canvas[..., 3] / 255.0
rim = cv2.dilate(alpha, np.ones((15, 15), np.uint8))
rim = cv2.GaussianBlur(rim, (0, 0), 1.5)
glow = cv2.GaussianBlur(cv2.dilate(alpha, np.ones((25, 25), np.uint8)), (0, 0), 10) * 0.8
B = 200
clean = cv2.copyMakeBorder(clean, B, B, B, B, cv2.BORDER_REPLICATE)
ox, oy = cx - (W + 2 * pad) // 2 + B, cy - (H + 2 * pad) // 2 + B
area = clean[oy:oy + H + 2 * pad, ox:ox + W + 2 * pad].astype(float)
for a, color in ((glow, (255, 255, 255)), (rim, (255, 255, 255))):
    area = area * (1 - a[..., None]) + np.array(color, float) * a[..., None]
area = area * (1 - alpha[..., None]) + canvas[..., :3] * alpha[..., None]
clean[oy:oy + H + 2 * pad, ox:ox + W + 2 * pad] = np.clip(area, 0, 255).astype(np.uint8)
clean = clean[B:-B, B:-B]
cv2.imwrite(out, clean, [cv2.IMWRITE_JPEG_QUALITY, 93])
cv2.imwrite(out + '-crop.png', clean[0:450, X0:X0 + 1000])
