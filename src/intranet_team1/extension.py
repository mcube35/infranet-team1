from db import mongo_db
import imghdr
from PIL import Image, ImageSequence
from io import BytesIO

def get_fs():
    from gridfs import GridFS
    return GridFS(mongo_db)

def to_safe_image(file):
    try:
        Image.open(file).verify()
        file.seek(0)
        image = Image.open(file)
        output = BytesIO()

        if image.format == "GIF":
            frames = [f.copy() for f in ImageSequence.Iterator(image)]
            if len(frames) > 1:
                frames[0].save(
                    output, format="GIF", save_all=True,
                    append_images=frames[1:], loop=0,
                    duration=image.info.get("duration", 100),
                    disposal=image.info.get("disposal", 2)
                )
            else:
                image.save(output, format="GIF")
        else:
            image = image.convert("RGB")
            img = Image.new(image.mode, image.size)
            img.putdata(list(image.getdata()))
            img.save(output, format="JPEG", quality=85)

        output.seek(0)
        return output
    except:
        return None

def is_allowed_image(file):
    filename = file.filename.lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

    if ext not in {"jpg", "jpeg", "png", "gif", "bmp", "webp"}:
        return False

    if not file.mimetype.startswith("image/"):
        return False

    file_head = file.read(512)
    file.seek(0)

    if imghdr.what(None, file_head) is None:
        return False

    return True

