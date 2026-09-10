
import cv2
import numpy as np
from tkinter import Tk, filedialog
from tkinter.filedialog import askdirectory
from PIL import Image
import matplotlib.pyplot as plt
import os
import pandas as pd
import seaborn as sns
from tqdm import tqdm
import math


# Select multiple images
Tk().withdraw()
file_paths = filedialog.askopenfilenames(
    title="Choose one or more images",
    filetypes=[("Images", ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tif", "*.tiff"))]
)

if not file_paths:
    print("No image selected. Exiting program.")
    exit()

# Global variables
drawing = False
img_preview = None
scale_x = scale_y = 1.0


#Color picker
COLOR_BOX = (0,0,0) #noir

step = 0

p0 = p1 = None
roi_width = 0

COLOR_BOX = (0, 0, 0)

def draw_oriented_roi(event, x, y, flags, param):
    global step, p0, p1, roi_width, img_preview, img_base, ux, uy, nx, ny

    # First click
    if event == cv2.EVENT_LBUTTONDOWN and step == 0:
        p0 = np.array([int(x * scale_x), int(y * scale_y)])
        step = 1

    # Orientation
    elif event == cv2.EVENT_MOUSEMOVE and step == 1:
        img_preview = img_base.copy()
        cv2.line(
            img_preview,
            (int(p0[0]/scale_x), int(p0[1]/scale_y)),
            (x, y),
            COLOR_BOX,
            1
        )

    elif event == cv2.EVENT_LBUTTONDOWN and step == 1:
        p1 = np.array([int(x * scale_x), int(y * scale_y)])
    
        dx, dy = p1 - p0
        length = np.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
    
        img_base = img_base.copy()
        cv2.line(
            img_base,
            (int(p0[0]/scale_x), int(p0[1]/scale_y)),
            (int(p1[0]/scale_x), int(p1[1]/scale_y)),
            COLOR_BOX,
            1
        )
    
        step = 2

    # Length
    elif event == cv2.EVENT_MOUSEMOVE and step == 2:
        img_preview = img_base.copy()
    
        pm = np.array([int(x * scale_x), int(y * scale_y)])
        roi_width_tmp = (pm - p1) @ np.array([nx, ny])
    
        p2 = p1 + np.array([nx, ny]) * roi_width_tmp
        p3 = p0 + np.array([nx, ny]) * roi_width_tmp
    
        box = np.array([p0, p1, p2, p3]) / [scale_x, scale_y]
        cv2.polylines(img_preview, [box.astype(int)], True, COLOR_BOX, 1)


    # Validation
    elif event == cv2.EVENT_LBUTTONUP and step == 2:
        pm = np.array([int(x * scale_x), int(y * scale_y)])
        roi_width = (pm - p1) @ np.array([nx, ny])
    
        p2 = p1 + np.array([nx, ny]) * roi_width
        p3 = p0 + np.array([nx, ny]) * roi_width
    
        box = np.array([p0, p1, p2, p3]) / [scale_x, scale_y]
    
        img_base = img_base.copy()
        cv2.polylines(img_base, [box.astype(int)], True, COLOR_BOX, 1)


    
    
    
# Define the region on the first image ---
first_image_path = file_paths[0]
img_full = cv2.cvtColor(
    np.array(Image.open(first_image_path)),
    cv2.COLOR_RGB2BGR
)

# Resize for screen if needed
screen_h = 900  # safe value for most screens
h, w = img_full.shape[:2]

if h > screen_h:
    scale = screen_h / h
    img_preview = cv2.resize(
        img_full,
        (int(w * scale), int(h * scale)),
        interpolation=cv2.INTER_AREA
    )
    scale_x = w / img_preview.shape[1]
    scale_y = h / img_preview.shape[0]

else:
    img_preview = img_full.copy()
img_base = img_preview.copy()


cv2.namedWindow("Define cropping zone")
cv2.setMouseCallback("Define cropping zone", draw_oriented_roi)

print("\nSélection ROI orientée :")
print(" - Clic 1 : point de départ")
print(" - Clic 2 : orientation / longueur")
print(" - Mouvement souris : largeur")
print(" - Entrée pour confirmer | 'x' pour annuler")

while True:
    cv2.imshow("Define cropping zone", img_preview)
    k = cv2.waitKey(1) & 0xFF

    if k == 13 and step == 2:  # ENTER
        break
    elif k == ord('x'):
        print("Cancelled")
        cv2.destroyAllWindows()
        exit()


cv2.destroyAllWindows()

# Apply the same zone to all images

if p0 is None or p1 is None or abs(roi_width) < 2:
    print("ROI invalid or too fine.")
    exit()

dx, dy = p1 - p0
roi_length = int(np.hypot(dx, dy))
ux, uy = dx / roi_length, dy / roi_length
nx, ny = -uy, ux

roi_width = int(abs(roi_width))

p2 = p1 + np.array([nx, ny]) * roi_width
p3 = p0 + np.array([nx, ny]) * roi_width

# Check which side is the longest
if roi_width > roi_length:
    roi_length, roi_width = roi_width, roi_length
    src_pts = np.array([p0, p3, p2, p1], dtype="float32")
else:
    src_pts = np.array([p0, p1, p2, p3], dtype="float32")

dst_pts = np.array([
    [0, 0],
    [roi_length, 0],
    [roi_length, roi_width],
    [0, roi_width]
], dtype="float32")

M = cv2.getPerspectiveTransform(src_pts, dst_pts)


# Image processing and profile extraction

profiles = pd.DataFrame()
sauvegarde = input("Sauvegarder les profils individuels ? (Y/N) ").upper()

for file_path in tqdm(file_paths, desc="Traitement", unit="image"):
    img = cv2.cvtColor(
        np.array(Image.open(file_path)),
        cv2.COLOR_RGB2BGR
    )

    cropped = cv2.warpPerspective(
        img,
        M,
        (roi_length, roi_width)
    )

    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    moyenne_colonnes = np.mean(gray, axis=0)
    profiles[file_path] = pd.Series(moyenne_colonnes)

    
    if sauvegarde == "Y":
        fig, (ax1, ax2) = plt.subplots(2,1, figsize=(8,6))
        ax1.imshow(gray, cmap='gray')
        ax1.axis("off")
        ax2.plot(moyenne_colonnes, color="darkred")
        plt.tight_layout()
        fig.savefig(file_path.rsplit('.',1)[0] + "_profile.jpg")
        plt.close(fig)


# CSV
print("/nChoose an output directory (can be on an external drive)")
output_dir = askdirectory(title='Choose the output directory')
os.makedirs(output_dir, exist_ok=True)

if not output_dir:
    print("No folder selected. End of program.")
    exit()


profiles_map = profiles.T
profiles_map.index = range(profiles.shape[1])

csv_path = os.path.join(output_dir, "all_profiles.csv")
profiles.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(f"\nCSV file saved under : {csv_path}")


# Heatmap Z-stack
plt.figure()
sns.heatmap(profiles_map,
            cmap="viridis",
            cbar_kws={"orientation": "horizontal", 'label': 'Light intensity (arbitrary unit)'},
            xticklabels=20)
    

plt.xlabel("X (pixels)")
plt.ylabel("Z (µm)")
plt.savefig(os.path.join(output_dir, 'zstack.png'), dpi=400)
plt.close()

# Annotated image
annot_img = cv2.cvtColor(np.array(Image.open(first_image_path)), cv2.COLOR_RGB2BGR)
cv2.polylines(annot_img,
              [src_pts.astype(int)],
              True,
              COLOR_BOX,
              2)

annot_path = os.path.join(output_dir, "cropping_zone.png")
cv2.imwrite(annot_path, annot_img)

print(f"Annotated image saved under : {annot_path}")