"""
تحويل صورة PNG إلى ICO
Convert PNG image to ICO format
"""
from PIL import Image

# فتح الصورة
img = Image.open(r"C:/Users/AbuDergham/.gemini/antigravity/brain/e3c4c407-cedb-402c-9433-2b0c326c9b7b/app_icon_1765462329149.png")

# تغيير الحجم إلى أحجام قياسية للأيقونة
sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# حفظ كملف ICO
img.save("icon.ico", format="ICO", sizes=sizes)

print("✓ Icon created successfully: icon.ico")
